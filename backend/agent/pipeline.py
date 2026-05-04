from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import numpy as np

from .prompts import DOMAIN_AGENT_CONFIG, build_prompt, CHAT_SYSTEM_PROMPT, EDUCATE_PROMPT
from .state_machine import DialogState, DialogStateMachine
from .session_manager import Session
from .domain_agent import DomainAgent
from core.search_engine import SearchEngine

TOP_K = 5
LOW_CONFIDENCE_THRESHOLD = 0.5
SUBSET_MIN_CANDIDATES = TOP_K * 2

# ---- 推理阶段的工作中短语 ----

PROGRESS_PHRASES = {
    "domain_detect":    "正在理解你的需求...",
    "extracting":       "正在分析图片特征，提取关键信息...",
    "condensing":       "正在浓缩检索文本，对齐描述格式...",
    "searching_subset": "正在候选图库中精准搜索...",
    "searching_full":   "正在数百万张图片中搜索最佳匹配...",
    "sorting":          "正在整理结果，按相似度排序...",
    "presenting":       "马上就好，正在准备展示结果...",
    "done":             "检索完成！",
    "chatting":         "正在思考如何回复你...",
}

# ---- 领域关键词库 ----

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

SEARCH_INTENT_KEYWORDS = [
    "帮我找", "搜索", "找一", "查找", "检索", "搜一", "帮我搜",
    "我想找", "我要找", "有没有", "看看", "找一张", "搜一下",
]

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

        if is_first:
            return await self._do_search(session, user_message, is_first=True)

        sm = session.state_machine
        intent = sm.user_intent(user_message)

        if intent == DialogState.DONE:
            sm.force(DialogState.DONE)
            session.touch()
            return self._reply(
                session,
                "很高兴能帮到你！如果需要搜索其他图片，随时告诉我。",
                state=DialogState.DONE,
                suggestions=["开始新的搜索"],
            )

        if intent == DialogState.REFINING:
            sm.force(DialogState.REFINING)
            session.touch()
            return await self._handle_refining(session, user_message)

        if intent == DialogState.EXPANDING:
            sm.force(DialogState.EXPANDING)
            session.touch()
            return await self._handle_expanding(session, user_message)

        if user_image is not None:
            return await self._do_search(session, user_message, is_first=False)

        if self._is_search_intent(user_message):
            return await self._do_search(session, user_message, is_first=False)

        sm.force(DialogState.CHATTING)
        session.touch()
        return await self._chat_reply(session, user_message)

    # ================================================================
    #  检索主流程
    # ================================================================

    async def _do_search(
        self,
        session: Session,
        user_message: str,
        is_first: bool = False,
    ) -> Dict[str, Any]:
        sm = session.state_machine
        reasoning_steps: List[str] = []
        progress_trail: List[str] = []

        # 领域检测
        progress_trail.append(PROGRESS_PHRASES["domain_detect"])
        detected_domain = self._detect_domain(user_message)
        if detected_domain != session.domain:
            old = session.domain
            session.domain = detected_domain
            reasoning_steps.append(f"领域切换：{old} → {detected_domain}")
        else:
            reasoning_steps.append(f"当前领域：{detected_domain}")

        domain = session.domain
        agent = self.domain_agents.get(domain)
        engine = self.engines.get(domain)
        if agent is None or engine is None:
            return self._error_reply(session, f"领域 '{domain}' 不可用")

        config = DOMAIN_AGENT_CONFIG.get(domain, DOMAIN_AGENT_CONFIG["auto"])
        has_attrs = config.get("has_structured_attrs", False)

        # Step 1
        sm.force(DialogState.EXTRACTING)
        session.touch()
        progress_trail.append(PROGRESS_PHRASES["extracting"])

        if has_attrs:
            extraction, step1_reasoning = await self._step1_extract(domain, agent, user_message)
            reasoning_steps.append(step1_reasoning)
        else:
            extraction = {"condensed_query": user_message[:20], "confidence": 0.8}
            reasoning_steps.append("auto/shop领域：直接使用查询文本")

        session.last_extraction = extraction

        # Step 2
        progress_trail.append(PROGRESS_PHRASES["condensing"])
        condensed_query = agent.condense_text(extraction, query=user_message)
        reasoning_steps.append(f"文本浓缩：「{condensed_query}」")

        # Step 3
        sm.force(DialogState.SEARCHING)
        session.touch()

        results, search_reasoning, is_low_confidence, strategy = await self._step3_search(
            domain, agent, engine, condensed_query, extraction
        )
        reasoning_steps.append(search_reasoning)
        progress_trail.append(
            PROGRESS_PHRASES["searching_subset"] if "子集" in strategy else PROGRESS_PHRASES["searching_full"]
        )
        session.last_results = results

        # Step 4
        sm.force(DialogState.PRESENTING)
        session.touch()
        progress_trail.append(PROGRESS_PHRASES["sorting"])

        suggestions = agent.generate_suggestions(results, is_low_confidence)
        suggestions.append("或者直接跟我聊天，描述你想要的图片")
        reply = self._format_reply(domain, results, is_low_confidence, extraction, is_first)

        progress_trail.append(PROGRESS_PHRASES["done"])

        return {
            "session_id": session.session_id,
            "state": sm.state.value,
            "reply": reply,
            "results": results,
            "reasoning_steps": reasoning_steps,
            "progress_trail": progress_trail,
            "suggestions": suggestions,
            "is_low_confidence": is_low_confidence,
            "domain": domain,
        }

    # ================================================================
    #  教育 / 科普 — 点击结果获取物种知识 + 同物种图片
    # ================================================================

    async def educate(
        self,
        session: Session,
        result_index: int,
    ) -> Dict[str, Any]:
        if not session.last_results or result_index >= len(session.last_results):
            return {"error": "无效的结果索引", "knowledge_text": "", "similar_images": []}

        result = session.last_results[result_index]
        domain = session.domain
        agent = self.domain_agents.get(domain)
        engine = self.engines.get(domain)

        if agent is None or engine is None:
            return {"error": f"领域不可用", "knowledge_text": "", "similar_images": []}

        # 提取物种/类别信息
        meta = result.get("meta", result)
        attrs = meta.get("attributes", {}) if isinstance(meta, dict) else {}
        caption = str(result.get("caption", "") or meta.get("caption", ""))

        species_id = attrs.get("species_id", "")
        class_name = attrs.get("class_name", "")
        scientific_name = meta.get("scientific_name", attrs.get("scientific_name", ""))
        chinese_name = meta.get("chinese_name", attrs.get("chinese_name", ""))
        class_name_cn = attrs.get("class_name_cn", "")

        # 查找同物种/类别图片
        similar_images: List[Dict[str, Any]] = []
        if domain == "plant" and species_id:
            indices = agent.find_candidate_indices([species_id])
            if indices:
                dummy_vec = np.zeros((1, 512), dtype="float32")
                similar_images = engine.search_in_subset(dummy_vec, indices, top_k=12)
                # 由于dummy_vec全为0，内积都为0，结果顺序即索引顺序，取前12个即可
                similar_images = similar_images[:12]

        elif domain == "animal" and class_name:
            indices = agent.find_candidate_indices([class_name])
            if indices:
                dummy_vec = np.zeros((1, 512), dtype="float32")
                similar_images = engine.search_in_subset(dummy_vec, indices, top_k=12)
                similar_images = similar_images[:12]

        # LLM 科普
        subject = chinese_name or class_name_cn or scientific_name or class_name or caption[:20]
        knowledge_text = ""
        if self.llm:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                prompt = EDUCATE_PROMPT.format(
                    subject=subject,
                    scientific_name=scientific_name or "未知",
                    domain=domain,
                    caption=caption,
                )
                msgs = [
                    SystemMessage(content="你是博学的自然知识科普助手。回复简洁有趣，2-3段即可。"),
                    HumanMessage(content=prompt),
                ]
                resp = await self.llm.ainvoke(msgs)
                knowledge_text = resp.content.strip()
            except Exception:
                knowledge_text = f"关于「{subject}」的详细信息暂时无法获取。"

        return {
            "knowledge_text": knowledge_text,
            "subject": subject,
            "scientific_name": scientific_name,
            "similar_images": similar_images,
            "main_image": result.get("image_url", ""),
            "domain": domain,
        }

    # ================================================================
    #  对话分支
    # ================================================================

    async def _handle_refining(self, session: Session, user_message: str) -> Dict[str, Any]:
        sm = session.state_machine
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

    async def _handle_expanding(self, session: Session, user_message: str) -> Dict[str, Any]:
        sm = session.state_machine
        domain = session.domain
        engine = self.engines.get(domain)
        if engine is None:
            return self._error_reply(session, "领域不可用")

        from core.processor import encode_single_text
        query = user_message[:20]
        text_vec = encode_single_text(self.model_loader.model, query, device=self.device)
        results = engine.search(text_vec, top_k=10)

        session.last_results = results
        sm.force(DialogState.PRESENTING)
        session.touch()

        return {
            "session_id": session.session_id,
            "state": sm.state.value,
            "reply": f"以下是更多相关结果（共 {len(results)} 条）：",
            "results": results,
            "reasoning_steps": ["扩大检索：返回更多候选"],
            "progress_trail": [PROGRESS_PHRASES["searching_full"], PROGRESS_PHRASES["done"]],
            "suggestions": ["如果还是没有满意的，试试换个关键词描述？"],
            "is_low_confidence": False,
            "domain": domain,
        }

    async def _chat_reply(self, session: Session, user_message: str) -> Dict[str, Any]:
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
            session, chat_reply, state=DialogState.CHATTING,
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
    #  领域检测
    # ================================================================

    def _detect_domain(self, query: str) -> str:
        scores: Dict[str, int] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query)
            if score > 0:
                scores[domain] = score
        if not scores:
            return "auto"
        return max(scores, key=scores.get)

    def _is_search_intent(self, query: str) -> bool:
        if any(kw in query for kw in SEARCH_INTENT_KEYWORDS):
            return True
        if any(kw in query for kw in VISUAL_DESCRIPTORS):
            return True
        if self._detect_domain(query) != "auto":
            return True
        if len(query) >= 8 and "?" not in query and "？" not in query:
            return True
        return False

    # ================================================================
    #  Step 1
    # ================================================================

    async def _step1_extract(self, domain: str, agent: DomainAgent, query: str) -> tuple:
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
            extraction = {"condensed_query": query[:20], "confidence": 0.3, "parse_error": str(e)[:100]}

        conf = extraction.get("confidence", 0.5)
        num_candidates = len(
            extraction.get("candidate_species_ids", [])
            or extraction.get("candidate_classes", [])
        )
        reasoning = f"LLM特征提取：confidence={conf:.2f}，候选数={num_candidates}，query_type={extraction.get('query_type', 'direct')}"
        return extraction, reasoning

    # ================================================================
    #  Step 3
    # ================================================================

    async def _step3_search(
        self, domain: str, agent: DomainAgent, engine: SearchEngine,
        condensed_query: str, extraction: Dict[str, Any],
    ) -> tuple:
        from core.processor import encode_single_text

        text_vec: np.ndarray = encode_single_text(self.model_loader.model, condensed_query, device=self.device)
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
                    strategy = "子集过滤检索"
                    results = engine.search_in_subset(text_vec, candidate_indices, top_k=TOP_K)

        if not results:
            strategy = "全量检索"
            results = engine.search(text_vec, top_k=TOP_K)

        is_low_confidence = False
        if results and results[0]["score"] < LOW_CONFIDENCE_THRESHOLD:
            is_low_confidence = True

        top_score = results[0]["score"] if results else 0.0
        reasoning = (
            f"CLIP+FAISS检索：策略={strategy}，Top-1相似度={top_score:.3f}，"
            f"{'低置信度(<0.5)!' if is_low_confidence else '置信度正常'}"
        )
        return results, reasoning, is_low_confidence, strategy

    # ================================================================
    #  Helpers
    # ================================================================

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    def _format_reply(self, domain: str, results: List[Dict[str, Any]],
                       is_low_confidence: bool, extraction: Dict[str, Any],
                       is_first: bool = False) -> str:
        domain_names = {"plant": "植物", "animal": "动物", "auto": "通用图片", "shop": "电商商品"}
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
            "session_id": session.session_id, "state": session.state,
            "reply": f"抱歉，{msg}。", "results": [],
            "reasoning_steps": [msg], "progress_trail": [],
            "suggestions": ["试试切换到另一个领域？"],
            "is_low_confidence": True, "domain": session.domain,
        }

    def _reply(self, session: Session, text: str, state: DialogState = DialogState.CHATTING,
               suggestions: Optional[List[str]] = None) -> Dict[str, Any]:
        return {
            "session_id": session.session_id, "state": state.value,
            "reply": text, "results": session.last_results,
            "reasoning_steps": [], "progress_trail": [PROGRESS_PHRASES["chatting"]],
            "suggestions": suggestions or [], "is_low_confidence": False,
            "domain": session.domain,
        }
