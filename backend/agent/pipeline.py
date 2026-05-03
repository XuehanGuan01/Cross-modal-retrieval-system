from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import numpy as np

from .prompts import DOMAIN_AGENT_CONFIG, build_prompt, CHAT_SYSTEM_PROMPT
from .state_machine import DialogState, DialogStateMachine
from .session_manager import Session
from .domain_agent import DomainAgent
from core.search_engine import SearchEngine

TOP_K = 5
LOW_CONFIDENCE_THRESHOLD = 0.5
SUBSET_MIN_CANDIDATES = TOP_K * 2  # 10


# ---- 领域关键词库（用于自动领域检测） ----

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "plant": [
        "花", "草", "树", "叶", "植物", "果实", "种子", "花瓣", "叶子",
        "开花", "草本", "木本", "灌木", "乔木", "野花", "野草", "草药",
        "玫瑰", "牡丹", "菊花", "兰花", "蒲公英", "松树", "竹子", "荷花",
        "梅花", "桃花", "樱花", "向日葵", "仙人掌", "蕨类", "苔藓",
        "茎", "根", "枝", "苗", "芽", "药材",
    ],
    "animal": [
        "动物", "鸟", "鱼", "狗", "猫", "马", "牛", "羊", "猪", "鸡", "鸭",
        "虎", "狮", "象", "猴", "蛇", "熊", "狼", "鹿", "兔", "鼠",
        "虫", "蝴蝶", "蜻蜓", "蜘蛛", "蚂蚁", "蜜蜂",
        "宠物", "野兽", "哺乳", "爬行", "两栖", "飞禽", "走兽",
        "斑马", "老虎", "狮子", "长颈鹿", "企鹅", "海豚", "鲸鱼", "鲨鱼",
        "老鹰", "孔雀", "天鹅", "松鼠", "刺猬", "考拉", "袋鼠", "熊猫",
    ],
    "shop": [
        "衣服", "裙子", "裤子", "鞋", "包", "手机", "电脑", "笔记本",
        "家具", "化妆品", "玩具", "首饰", "手表", "眼镜", "帽子",
        "连衣裙", "T恤", "运动鞋", "高跟鞋", "衬衫", "外套", "羽绒服",
        "商品", "购物", "电商", "淘宝", "网购", "品牌",
        "口红", "香水", "项链", "戒指", "耳环", "手链",
        "沙发", "桌子", "椅子", "床", "灯具", "窗帘",
    ],
}

# 搜索意图关键词
SEARCH_INTENT_KEYWORDS = [
    "帮我找", "搜索", "找一", "查找", "检索", "搜一", "帮我搜",
    "我想找", "我要找", "有没有", "看看", "找一张", "搜一下",
]

# 视觉描述词（含这些词大概率是搜索意图）
VISUAL_DESCRIPTORS = [
    "红色", "黄色", "蓝色", "绿色", "白色", "黑色", "紫色", "粉色", "灰色",
    "橙色", "棕色", "金色", "银色", "彩色",
    "圆形", "方形", "长条", "扁", "大", "小", "细", "粗", "尖", "心形",
    "条纹", "斑点", "花纹", "格子", "纯色",
    "毛茸茸", "光滑", "粗糙",
]


class AgentPipeline:
    def __init__(
        self,
        llm,
        engines: Dict[str, SearchEngine],
        domain_agents: Dict[str, DomainAgent],
        model_loader,
        device: str,
    ):
        self.llm = llm
        self.engines = engines
        self.domain_agents = domain_agents
        self.model_loader = model_loader
        self.device = device

    # ================================================================
    #  主入口
    # ================================================================

    async def run(
        self,
        session: Session,
        user_message: str,
        user_image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        is_first = (len(session.messages) == 0)

        # ---- 第一条消息：强制检索 ----
        if is_first:
            return await self._do_search(session, user_message, is_first=True)

        # ---- 后续消息：意图分支 ----
        sm = session.state_machine
        intent = sm.user_intent(user_message)

        # 分支1：用户确认 → 结束
        if intent == DialogState.DONE:
            sm.force(DialogState.DONE)
            session.touch()
            return self._reply(
                session,
                "很高兴能帮到你！如果需要搜索其他图片，随时告诉我。",
                state=DialogState.DONE,
                suggestions=["开始新的搜索"],
            )

        # 分支2：细化条件 → 以对话方式询问细节，然后检索
        if intent == DialogState.REFINING:
            sm.force(DialogState.REFINING)
            session.touch()
            return await self._handle_refining(session, user_message)

        # 分支3：扩大搜索 → 放宽条件重新检索
        if intent == DialogState.EXPANDING:
            sm.force(DialogState.EXPANDING)
            session.touch()
            return await self._handle_expanding(session, user_message)

        # 分支4：用户上传了图片 → 以图搜图模式
        if user_image is not None:
            return await self._do_search(session, user_message, is_first=False)

        # 分支5：判断是否搜索意图
        if self._is_search_intent(user_message):
            return await self._do_search(session, user_message, is_first=False)

        # 分支6：不确定 → 聊天式响应，引导用户
        sm.force(DialogState.CHATTING)
        session.touch()
        return await self._chat_reply(session, user_message)

    # ================================================================
    #  检索主流程（4步 Pipeline）
    # ================================================================

    async def _do_search(
        self,
        session: Session,
        user_message: str,
        is_first: bool = False,
    ) -> Dict[str, Any]:
        sm = session.state_machine
        reasoning_steps: List[str] = []

        # ★ 领域自动检测（关键词规则，非 LLM）
        detected_domain = self._detect_domain(user_message)
        if detected_domain != session.domain:
            old = session.domain
            session.domain = detected_domain
            reasoning_steps.append(
                f"领域切换：{old} → {detected_domain}（检测到关键词）"
            )
        else:
            reasoning_steps.append(f"当前领域：{detected_domain}")

        domain = session.domain
        agent = self.domain_agents.get(domain)
        engine = self.engines.get(domain)
        if agent is None or engine is None:
            return self._error_reply(session, f"领域 '{domain}' 不可用")

        config = DOMAIN_AGENT_CONFIG.get(domain, DOMAIN_AGENT_CONFIG["auto"])
        has_attrs = config.get("has_structured_attrs", False)

        # ---- Step 1: LLM Feature Extraction ----
        sm.force(DialogState.EXTRACTING)
        session.touch()

        if has_attrs:
            extraction, step1_reasoning = await self._step1_extract(
                domain, agent, user_message
            )
            reasoning_steps.append(step1_reasoning)
        else:
            extraction = {
                "condensed_query": user_message[:20],
                "confidence": 0.8,
            }
            reasoning_steps.append(
                f"auto/shop领域：直接使用查询文本"
            )

        session.last_extraction = extraction

        # ---- Step 2: Text Condensation ----
        condensed_query = agent.condense_text(extraction, query=user_message)
        reasoning_steps.append(
            f"文本浓缩：「{condensed_query}」"
        )

        # ---- Step 3: CLIP + FAISS ----
        sm.force(DialogState.SEARCHING)
        session.touch()

        results, search_reasoning, is_low_confidence = await self._step3_search(
            domain, agent, engine, condensed_query, extraction
        )
        reasoning_steps.append(search_reasoning)
        session.last_results = results

        # ---- Step 4: Result + Suggestions ----
        sm.force(DialogState.PRESENTING)
        session.touch()

        suggestions = agent.generate_suggestions(results, is_low_confidence)
        suggestions.append("或者直接跟我聊天，描述你想要的图片")
        reply = self._format_reply(domain, results, is_low_confidence, extraction, is_first)

        return {
            "session_id": session.session_id,
            "state": sm.state.value,
            "reply": reply,
            "results": results,
            "reasoning_steps": reasoning_steps,
            "suggestions": suggestions,
            "is_low_confidence": is_low_confidence,
            "domain": domain,
        }

    # ================================================================
    #  对话分支处理
    # ================================================================

    async def _handle_refining(
        self, session: Session, user_message: str
    ) -> Dict[str, Any]:
        """用户说'不对/再找' → 以细化后的描述重新检索"""
        sm = session.state_machine

        # 如果 LLM 可用，让 LLM 理解用户的细化需求
        if self.llm:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                refine_prompt = (
                    "用户对上次搜索结果不满意。请根据用户的反馈，提取出新的搜索关键词（≤20字）。"
                    "只输出关键词文本，不要加任何解释。"
                )
                msgs = [
                    SystemMessage(content=refine_prompt),
                    HumanMessage(content=f"上次搜索：{session.last_extraction}\n用户反馈：{user_message}"),
                ]
                resp = await self.llm.ainvoke(msgs)
                refined_query = resp.content.strip()[:20]
            except Exception:
                refined_query = user_message[:20]
        else:
            refined_query = user_message[:20]

        sm.force(DialogState.EXTRACTING)
        return await self._do_search(session, refined_query, is_first=False)

    async def _handle_expanding(
        self, session: Session, user_message: str
    ) -> Dict[str, Any]:
        """用户说'还有/其他' → 显示更多结果"""
        sm = session.state_machine

        # 扩大检索：直接全量搜索，不限制候选
        domain = session.domain
        engine = self.engines.get(domain)
        if engine is None:
            return self._error_reply(session, f"领域不可用")

        from core.processor import encode_single_text
        query = user_message[:20]
        text_vec = encode_single_text(self.model_loader.model, query, device=self.device)
        results = engine.search(text_vec, top_k=10)  # 返回更多

        session.last_results = results
        sm.force(DialogState.PRESENTING)
        session.touch()

        return {
            "session_id": session.session_id,
            "state": sm.state.value,
            "reply": f"以下是更多相关结果（共 {len(results)} 条）：",
            "results": results,
            "reasoning_steps": ["扩大检索：返回更多候选"],
            "suggestions": ["如果还是没有满意的，试试换个关键词描述？"],
            "is_low_confidence": False,
            "domain": domain,
        }

    async def _chat_reply(
        self, session: Session, user_message: str
    ) -> Dict[str, Any]:
        """非搜索的聊天消息 → 自然回复 + 引导搜索"""
        if self.llm:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                msgs = [
                    SystemMessage(content=CHAT_SYSTEM_PROMPT),
                    HumanMessage(content=user_message),
                ]
                resp = await self.llm.ainvoke(msgs)
                chat_reply = resp.content.strip()
            except Exception:
                chat_reply = self._fallback_chat_reply()
        else:
            chat_reply = self._fallback_chat_reply()

        return self._reply(
            session,
            chat_reply,
            state=DialogState.CHATTING,
            suggestions=[
                "帮我找一种开黄色小花的植物",
                "找一只黑白条纹的动物",
                "帮我找红色的连衣裙",
            ],
        )

    def _fallback_chat_reply(self) -> str:
        return (
            "我是'跨模态多领域·交互式Agent'，可以帮你在植物、动物、电商商品、通用图片"
            "四个领域中搜索图片。\n\n"
            "你可以直接描述你想找的图片，比如：\n"
            '- "帮我找一种开黄色小花的植物"\n'
            '- "找一只黑白条纹的动物"\n'
            '- "帮我找红色的连衣裙"\n\n'
            "试试看吧！"
        )

    # ================================================================
    #  领域检测（关键词规则）
    # ================================================================

    def _detect_domain(self, query: str) -> str:
        """根据关键词检测领域，匹配不上则返回 auto"""
        scores: Dict[str, int] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query)
            if score > 0:
                scores[domain] = score

        if not scores:
            return "auto"

        # 返回匹配关键词最多的领域
        best = max(scores, key=scores.get)
        return best

    # ================================================================
    #  搜索意图检测
    # ================================================================

    def _is_search_intent(self, query: str) -> bool:
        # 显式搜索关键词
        if any(kw in query for kw in SEARCH_INTENT_KEYWORDS):
            return True
        # 包含视觉描述词
        if any(kw in query for kw in VISUAL_DESCRIPTORS):
            return True
        # 领域关键词命中
        if self._detect_domain(query) != "auto":
            return True
        # 长度 > 5 字且不包含问号 → 大概率是搜索
        if len(query) >= 8 and "?" not in query and "?" not in query:
            return True
        return False

    # ================================================================
    #  Step 1: LLM 特征提取
    # ================================================================

    async def _step1_extract(
        self,
        domain: str,
        agent: DomainAgent,
        query: str,
    ) -> tuple:
        knowledge_text = agent.knowledge_text()
        prompts = build_prompt(domain, query, knowledge_text)

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=prompts["system"]),
                HumanMessage(content=prompts["user"]),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            content = self._clean_json(content)
            extraction = json.loads(content)
        except Exception as e:
            extraction = {
                "condensed_query": query[:20],
                "confidence": 0.3,
                "parse_error": str(e)[:100],
            }

        conf = extraction.get("confidence", 0.5)
        num_candidates = len(
            extraction.get("candidate_species_ids", [])
            or extraction.get("candidate_classes", [])
        )
        reasoning = (
            f"LLM特征提取：confidence={conf:.2f}，"
            f"候选数={num_candidates}，"
            f"query_type={extraction.get('query_type', 'direct')}"
        )
        return extraction, reasoning

    # ================================================================
    #  Step 3: CLIP + FAISS 检索
    # ================================================================

    async def _step3_search(
        self,
        domain: str,
        agent: DomainAgent,
        engine: SearchEngine,
        condensed_query: str,
        extraction: Dict[str, Any],
    ) -> tuple:
        from core.processor import encode_single_text

        text_vec: np.ndarray = encode_single_text(
            self.model_loader.model,
            condensed_query,
            device=self.device,
        )

        config = DOMAIN_AGENT_CONFIG.get(domain, {})
        has_attrs = config.get("has_structured_attrs", False)

        results: List[Dict[str, Any]] = []
        strategy = "全量检索"

        if has_attrs:
            candidate_key = config.get("candidate_key", "")
            candidate_ids = extraction.get(candidate_key, [])
            if candidate_ids and len(candidate_ids) > 0:
                candidate_indices = agent.find_candidate_indices(candidate_ids)
                if len(candidate_indices) >= SUBSET_MIN_CANDIDATES:
                    strategy = f"子集过滤检索（{len(candidate_indices)} 张候选）"
                    results = engine.search_in_subset(
                        text_vec, candidate_indices, top_k=TOP_K
                    )

        if not results:
            strategy = "全量检索"
            results = engine.search(text_vec, top_k=TOP_K)

        is_low_confidence = False
        if results and results[0]["score"] < LOW_CONFIDENCE_THRESHOLD:
            is_low_confidence = True

        top_score = results[0]["score"] if results else 0.0
        reasoning = (
            f"CLIP+FAISS检索：策略={strategy}，"
            f"Top-1相似度={top_score:.3f}，"
            f"{'低置信度(<0.5)!' if is_low_confidence else '置信度正常'}"
        )
        return results, reasoning, is_low_confidence

    # ================================================================
    #  Helpers
    # ================================================================

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    def _format_reply(
        self,
        domain: str,
        results: List[Dict[str, Any]],
        is_low_confidence: bool,
        extraction: Dict[str, Any],
        is_first: bool = False,
    ) -> str:
        domain_names = {
            "plant": "植物", "animal": "动物", "auto": "通用图片", "shop": "电商商品"
        }
        dn = domain_names.get(domain, domain)

        switch_hint = ""
        if domain == "auto" and is_first:
            switch_hint = (
                "\n\n💡 提示：如果你要找的是植物、动物或商品类图片，请在描述中加入相关关键词，"
                "我会自动切换到对应领域进行精准检索。"
            )

        if is_low_confidence:
            prefix = f"我在「{dn}」领域中搜索了你的描述，但匹配度较低。你可以补充更多细节吗？"
        elif not results:
            prefix = f"在「{dn}」领域中没有找到匹配的结果，试试换一种描述方式？"
        else:
            prefix = f"根据你的描述，我在「{dn}」领域中找到 {len(results)} 个候选结果。"

        if results:
            top_items = []
            for r in results[:3]:
                cap = r.get("caption", "") or ""
                cap_short = cap[:30].strip()
                score = r.get("score", 0)
                top_items.append(f"  #{r['rank']} (相似度 {score:.3f}): {cap_short}")
            prefix += "\n\nTop-3：\n" + "\n".join(top_items)

        reasons = extraction.get("reasoning", "")
        if reasons:
            prefix += f"\n\n推理依据：{reasons}"

        if switch_hint:
            prefix += switch_hint

        return prefix

    def _error_reply(self, session: Session, msg: str) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "state": session.state,
            "reply": f"抱歉，{msg}。",
            "results": [],
            "reasoning_steps": [msg],
            "suggestions": ["试试切换到另一个领域？"],
            "is_low_confidence": True,
            "domain": session.domain,
        }

    def _reply(
        self,
        session: Session,
        text: str,
        state: DialogState = DialogState.CHATTING,
        suggestions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "state": state.value,
            "reply": text,
            "results": session.last_results,
            "reasoning_steps": [],
            "suggestions": suggestions or [],
            "is_low_confidence": False,
            "domain": session.domain,
        }
