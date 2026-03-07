"""Claude prompts for visual tile generation."""

DECK_SELECTOR_PROMPT = """Given this contact context, pick the single best deck type
and return ONLY the type name:

- hook: Lead has a pain point, needs re-engagement
- roi: Lead pushed back on pricing or needs internal justification
- proof: Lead wants social proof, case studies, or validation
- personal: Strong personal connection captured (school, hobby, mutual contact)
- competitive: Lead evaluating alternatives or using a competitor

Context:
{context}

Return ONLY one word: hook, roi, proof, personal, or competitive."""


TILE_CONTENT_PROMPT = """Generate content for a {deck_type} deck.

Contact context:
{context}

{hint_section}

DECK GUIDELINES:
{deck_guidelines}

Return ONLY valid JSON — an array of tile objects. Each tile has:
{{
    "type": "cover|stat|list|comparison|math|timeline|quote|metrics|cta|personal|bridge|gain",
    "tag": "short label like CASE STUDY or ROI BREAKDOWN (optional)",
    "headline": "short punchy headline (under 8 words)",
    "stat": "number if applicable",
    "stat_label": "what the number means",
    "source": "credibility citation if using a stat",
    "body": "supporting text (under 25 words)",
    "items": [
        {{"label": "...", "value": "...", "old_value": "...", "icon": "emoji"}}
    ],
    "cta_text": "button text for CTA tiles",
    "accent": "{accent_hex}"
}}

Rules:
- Stats should be real and defensible (use well-known industry benchmarks)
- Headlines under 8 words
- Body text under 25 words per tile
- Items arrays max 4 entries
- CTA should feel low-pressure and reference something personal if possible
- The deck tells a STORY — each tile builds on the last
- Return ONLY the JSON array, no markdown fences"""


DECK_GUIDELINES = {
    "hook": """HOOK DECK — 5 tiles:
1. cover: Bold headline naming the pain. Tag like "THE CHALLENGE"
2. stat: One massive surprising stat about their industry
3. list: 3 warning signs / symptoms the lead will recognize
4. comparison: Legacy vs modern approach (old_value vs value)
5. cta: Personal, low-pressure ask referencing the conversation""",

    "roi": """ROI DECK — 5 tiles:
1. cover: "The Real Cost of Doing Nothing" framing
2. stat: Industry-level cost figure
3. math: Personalized calculation using their team size/details
4. timeline: Visual payback roadmap (Week 1, Month 1, Month 3, Month 6)
5. cta: "Share this with your VP?" — designed to be forwarded""",

    "proof": """PROOF DECK — 4 tiles:
1. cover: "How a [Similar Company] Cut Their [Metric] by X%"
2. quote: Customer testimonial in large italic type
3. metrics: Before/after comparison with 3 key metrics
4. cta: "Your team is the same size" — specific similarity callout""",

    "personal": """PERSONAL DECK — 3 tiles:
1. personal: Leads with the personal connection (emoji + bold headline)
2. bridge: One sentence transitioning personal to professional
3. cta: Casual ask, like texting a friend""",

    "competitive": """COMPETITIVE DECK — 4 tiles:
1. cover: "Thinking about switching? Here's what changes."
2. comparison: Feature-by-feature, their side grayed/muted, yours highlighted
3. gain: What they'd GET in the first 90 days (not what they're missing)
4. cta: Zero-risk framing — "Run both side by side for a week" """,
}


ACCENT_COLORS = {
    "hook": "#A78BFA",
    "roi": "#38BDF8",
    "proof": "#4ADE80",
    "personal": "#F59E0B",
    "competitive": "#64748B",
}


# Background gradients per deck type (progressively lighter per tile)
DECK_GRADIENTS = {
    "hook": [
        "linear-gradient(145deg, #0F0A2E 0%, #1A1145 50%, #2D1B69 100%)",
        "linear-gradient(145deg, #120D33 0%, #1D1350 50%, #321F72 100%)",
        "linear-gradient(145deg, #150F38 0%, #201755 50%, #37237B 100%)",
        "linear-gradient(145deg, #181242 0%, #231B5A 50%, #3C2784 100%)",
        "linear-gradient(145deg, #1B144A 0%, #261F5F 50%, #412B8D 100%)",
    ],
    "roi": [
        "linear-gradient(145deg, #0A1628 0%, #0F1F3A 50%, #162D52 100%)",
        "linear-gradient(145deg, #0C1A2E 0%, #112340 50%, #1A3460 100%)",
        "linear-gradient(145deg, #0E1E34 0%, #132746 50%, #1E3B6E 100%)",
        "linear-gradient(145deg, #102238 0%, #152B4C 50%, #22427C 100%)",
        "linear-gradient(145deg, #12263E 0%, #172F52 50%, #26498A 100%)",
    ],
    "proof": [
        "linear-gradient(145deg, #0A1F14 0%, #0F2E1E 50%, #163D2A 100%)",
        "linear-gradient(145deg, #0C2318 0%, #113222 50%, #1A442F 100%)",
        "linear-gradient(145deg, #0E271C 0%, #133626 50%, #1E4B34 100%)",
        "linear-gradient(145deg, #102B20 0%, #153A2A 50%, #225239 100%)",
    ],
    "personal": [
        "linear-gradient(145deg, #1A1520 0%, #2A2035 50%, #3D2E4D 100%)",
        "linear-gradient(145deg, #1E1924 0%, #2E243A 50%, #443356 100%)",
        "linear-gradient(145deg, #221D28 0%, #32283F 50%, #4B385F 100%)",
    ],
    "competitive": [
        "linear-gradient(145deg, #0F1318 0%, #1A2028 50%, #252D38 100%)",
        "linear-gradient(145deg, #12161C 0%, #1D242E 50%, #2A333F 100%)",
        "linear-gradient(145deg, #151A20 0%, #202834 50%, #2F3946 100%)",
        "linear-gradient(145deg, #181E24 0%, #232C3A 50%, #343F4D 100%)",
    ],
}
