"""
APUSH MCQ Web App
- Flask backend with Claude API integration
- One stimulus → 3 questions (AP exam format)
- Uses student's PDF notes as context for Claude generation
- Beautiful web UI with buttons
"""

import os
import sys
import json
import random
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

app = Flask(__name__)

# Claude API is optional — only needed for generated questions
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))
client = None
if HAS_API_KEY:
    import anthropic
    client = anthropic.Anthropic()

# ─── Load PDF notes ────────────────────────────────────────────────────────────
NOTES_PATH = os.path.join(os.path.dirname(__file__), "unit_notes.json")
UNIT_NOTES = {}
if os.path.exists(NOTES_PATH):
    with open(NOTES_PATH, "r", encoding="utf-8") as f:
        UNIT_NOTES = json.load(f)

# ─── Load exam stimuli ─────────────────────────────────────────────────────────
EXAM_STIMULI_PATH = os.path.join(os.path.dirname(__file__), "exam_sets.json")
EXAM_STIMULI = []
if os.path.exists(EXAM_STIMULI_PATH):
    with open(EXAM_STIMULI_PATH, "r", encoding="utf-8") as f:
        EXAM_STIMULI = json.load(f)

# ─── Load HSTP (highschooltestprep.com) stimuli ────────────────────────────────
HSTP_STIMULI_PATH = os.path.join(os.path.dirname(__file__), "hstp_stimuli.json")
HSTP_STIMULI = []
if os.path.exists(HSTP_STIMULI_PATH):
    with open(HSTP_STIMULI_PATH, "r", encoding="utf-8") as f:
        HSTP_STIMULI = json.load(f)

# ─── Period metadata ───────────────────────────────────────────────────────────
PERIODS = {
    1: {"range": "1491–1607", "name": "Pre-Columbian & Early Contact"},
    2: {"range": "1607–1754", "name": "Colonial America"},
    3: {"range": "1754–1800", "name": "Revolution & Early Republic"},
    4: {"range": "1800–1848", "name": "Democracy & Manifest Destiny"},
    5: {"range": "1844–1877", "name": "Civil War & Reconstruction"},
    6: {"range": "1865–1898", "name": "Gilded Age & Industrialization"},
    7: {"range": "1890–1945", "name": "Progressive Era to WWII"},
    8: {"range": "1945–1980", "name": "Cold War, Civil Rights & Vietnam"},
    9: {"range": "1980–Present", "name": "Reagan Era to Today"},
}

# ─── Pre-written question sets (1 stimulus → 3 questions) ─────────────────────
# Each set has: period, stimulus, questions: [{stem, choices, answer, explanation, skill, reasoning}]
PREWRITTEN_SETS = [
    # ── PERIOD 1 ──
    {
        "period": 1,
        "stimulus": (
            "Archaeological evidence from Cahokia (near present-day St. Louis) reveals a city "
            "that at its peak around 1100 CE housed an estimated 10,000–20,000 people, larger "
            "than contemporary London. The site features massive earthen mounds, a central "
            "plaza, and evidence of long-distance trade in copper, mica, and shells. The city "
            "declined sharply after 1200 CE, likely due to environmental degradation."
        ),
        "questions": [
            {
                "stem": "The archaeological evidence from Cahokia most directly challenges which common assumption about pre-Columbian North America?",
                "choices": ["That Native Americans engaged in long-distance trade networks",
                            "That complex, densely populated urban societies did not exist north of Mexico",
                            "That environmental factors played no role in the collapse of Native civilizations",
                            "That Mississippian culture was largely isolated from Mesoamerican influence"],
                "answer": "B",
                "explanation": "Cahokia's scale—rivaling major European cities—directly contradicts the assumption that sophisticated urban civilization was confined to Mesoamerica and South America.",
                "skill": "Claims & Evidence",
                "reasoning": "Contextualization",
            },
            {
                "stem": "The decline of Cahokia after 1200 CE most directly illustrates which broader pattern in Native American history?",
                "choices": ["The inability of Native American societies to sustain urban populations",
                            "The vulnerability of complex societies to environmental and political pressures",
                            "The impact of European diseases on indigenous populations before direct contact",
                            "The cyclical nature of warfare among competing Native American city-states"],
                "answer": "B",
                "explanation": "Cahokia's decline shows that complex indigenous societies, like all civilizations, were vulnerable to environmental strain and internal political instability—not that they were inherently unstable.",
                "skill": "Making Connections",
                "reasoning": "Causation",
            },
            {
                "stem": "Evidence of long-distance trade in copper, mica, and shells at Cahokia most directly supports which conclusion?",
                "choices": ["Cahokia functioned as the political capital of a centralized Native American empire",
                            "Pre-Columbian North Americans had developed extensive interregional exchange networks",
                            "Mississippian peoples had established maritime trade routes along the Gulf Coast",
                            "Native American economies were primarily based on luxury goods rather than agriculture"],
                "answer": "B",
                "explanation": "Trade goods from distant regions demonstrate well-developed exchange networks across North America, though this does not necessarily imply centralized political control (A) or maritime trade (C).",
                "skill": "Claims & Evidence",
                "reasoning": "Causation",
            },
        ],
    },
    {
        "period": 1,
        "stimulus": (
            "\"They brought us parrots and balls of cotton and spears and many other things, "
            "which they exchanged for the glass beads and hawks' bells. They willingly traded "
            "everything they owned... They do not bear arms, and do not know them, for I showed "
            "them a sword, they took it by the edge and cut themselves out of ignorance... "
            "With fifty men we could subjugate them all and make them do whatever we want.\"\n"
            "— Christopher Columbus, Journal, October 1492"
        ),
        "questions": [
            {
                "stem": "Columbus's observations most directly reflect which motivation shaping early Spanish colonial policy?",
                "choices": ["A desire to establish peaceful commercial partnerships with indigenous peoples",
                            "The belief that Native peoples were sophisticated equals requiring diplomacy",
                            "The drive to exploit indigenous labor and resources for imperial profit",
                            "A commitment to Christian missionary work as the primary goal of colonization"],
                "answer": "C",
                "explanation": "Columbus immediately assesses Native peoples in terms of their exploitability—noting their lack of weapons and imagining 'fifty men' could subjugate them, foreshadowing the encomienda system.",
                "skill": "Sourcing & Situation",
                "reasoning": "Contextualization",
            },
            {
                "stem": "A historian would most likely use Columbus's journal entry as evidence for which argument?",
                "choices": ["European technological superiority made colonial conquest inevitable",
                            "European perceptions of indigenous 'naivety' served to justify colonial exploitation",
                            "Native Americans deliberately deceived European explorers about their capabilities",
                            "The Columbian Exchange began with mutually beneficial trade relationships"],
                "answer": "B",
                "explanation": "Columbus frames Native generosity and unfamiliarity with swords as evidence of inferiority and subjugability—demonstrating how European perceptions, not objective reality, justified exploitation.",
                "skill": "Argumentation",
                "reasoning": "Causation",
            },
            {
                "stem": "Which of the following best explains a limitation of Columbus's journal as a historical source?",
                "choices": ["Columbus lacked the education needed to accurately describe what he observed",
                            "The journal was written decades after the events it describes",
                            "Columbus's perspective was shaped by his goals of gaining royal patronage and funding",
                            "The journal was intended for a Native American audience"],
                "answer": "C",
                "explanation": "Columbus wrote for Ferdinand and Isabella, who funded his voyage. His descriptions emphasize the ease of subjugation and wealth potential—framing that served his need to prove the voyage's value to his patrons.",
                "skill": "Sourcing & Situation",
                "reasoning": "Contextualization",
            },
        ],
    },

    # ── PERIOD 2 ──
    {
        "period": 2,
        "stimulus": (
            "\"We appeal to all free men: that the poverty of Virginia is caused not by the "
            "Indians but by those great men who oppress us, who have monopolized the best lands, "
            "who send their servants armed against us when we dare to protest. We demand that "
            "our servants who have completed their indentures receive the land they were promised, "
            "and that the Indian frontier be opened for settlement.\"\n"
            "— Nathaniel Bacon, Declaration of the People, 1676 (paraphrased)"
        ),
        "questions": [
            {
                "stem": "Bacon's Rebellion most directly revealed which underlying tension in Chesapeake colonial society?",
                "choices": ["Religious conflict between Anglican settlers and dissenting Puritan communities",
                            "Economic grievances of landless freedmen against the planter elite",
                            "Resistance among indentured servants to the extension of their contracts",
                            "Conflict between tobacco planters and merchants over export trade control"],
                "answer": "B",
                "explanation": "Bacon's coalition included freed servants who found good land monopolized by large planters. The rebellion exposed the instability of producing armed, landless, resentful freedmen.",
                "skill": "Sourcing & Situation",
                "reasoning": "Causation",
            },
            {
                "stem": "Bacon's Rebellion most directly contributed to which long-term change in Virginia's labor system?",
                "choices": ["The elimination of indentured servitude in favor of free wage labor",
                            "The accelerated transition from indentured servitude to African chattel slavery",
                            "The expansion of colonial self-governance through elected assemblies",
                            "Stricter enforcement of land distribution promises to freed servants"],
                "answer": "B",
                "explanation": "After Bacon's Rebellion demonstrated the danger of a large class of armed white freedmen, planters increasingly turned to enslaved Africans—a permanently bound workforce that could not claim rights as Englishmen.",
                "skill": "Making Connections",
                "reasoning": "Causation",
            },
            {
                "stem": "Bacon's appeal to 'all free men' while simultaneously demanding that 'the Indian frontier be opened' reveals which contradiction in his movement?",
                "choices": ["A commitment to democratic reform that excluded women from political participation",
                            "An anti-elite populism that was simultaneously built on dispossessing Native Americans",
                            "A desire for religious freedom that did not extend to non-Christian peoples",
                            "An economic vision that relied on expanding the institution of indentured servitude"],
                "answer": "B",
                "explanation": "Bacon framed his rebellion as populist resistance to elite oppression, yet his proposed solution—opening Native lands—required violent dispossession of indigenous peoples. The rebellion was anti-elite but not anti-colonial.",
                "skill": "Claims & Evidence",
                "reasoning": "Comparison",
            },
        ],
    },
    {
        "period": 2,
        "stimulus": (
            "\"Brethren, you are by nature children of wrath. Your hearts are corrupt, deceitful "
            "above all things. Yet God in His infinite mercy has chosen some among you—not because "
            "of your worthiness, but by His sovereign grace alone—to receive the gift of new birth. "
            "Have you felt that stirring within you? Do not trust in your church membership or your "
            "moral conduct—trust only in that direct experience of God's transforming power.\"\n"
            "— George Whitefield, sermon, Philadelphia, 1740 (paraphrased)"
        ),
        "questions": [
            {
                "stem": "Whitefield's preaching most directly contributed to which social development in colonial America?",
                "choices": ["The consolidation of church authority as congregations rallied around established ministers",
                            "The weakening of traditional religious hierarchies as individuals claimed direct spiritual authority",
                            "The decline of Calvinist theology in favor of Arminian doctrines emphasizing free will",
                            "The unification of colonial denominations into a single American Protestant church"],
                "answer": "B",
                "explanation": "Great Awakening revivalists bypassed established church structures, preaching that individual conversion—not church membership or clergy approval—was true faith, democratizing religious authority.",
                "skill": "Sourcing & Situation",
                "reasoning": "Causation",
            },
            {
                "stem": "The Great Awakening's emphasis on individual religious experience most directly foreshadowed which later development?",
                "choices": ["The establishment of Anglicanism as the official religion of the new United States",
                            "Revolutionary-era challenges to political authority and traditional hierarchies",
                            "The immediate abolition of slavery in response to evangelical moral arguments",
                            "The decline of religious participation in American public life"],
                "answer": "B",
                "explanation": "By encouraging colonists to question established religious authority and trust personal judgment, the Great Awakening fostered a broader culture of challenging traditional hierarchies—including political ones.",
                "skill": "Making Connections",
                "reasoning": "Continuity & Change Over Time",
            },
            {
                "stem": "Whitefield's message that salvation depended on personal experience 'not church membership or moral conduct' most directly challenged which group?",
                "choices": ["Quakers who rejected all forms of organized worship",
                            "Established Congregationalist and Anglican clergy who controlled access to church membership",
                            "Deists who rejected the idea of divine intervention entirely",
                            "Catholic missionaries competing for Native American converts"],
                "answer": "B",
                "explanation": "Established clergy derived their authority from controlling church membership and interpreting scripture. Whitefield's message that these were irrelevant to salvation directly undermined their social position.",
                "skill": "Contextualization",
                "reasoning": "Causation",
            },
        ],
    },

    # ── PERIOD 3 ──
    {
        "period": 3,
        "stimulus": (
            "\"The sun never shined on a cause of greater worth. 'Tis not the affair of a city, "
            "a county, a province, or a kingdom, but of a continent—of at least one eighth part "
            "of the habitable globe. 'Tis not the concern of a day, a year, or an age; posterity "
            "are virtually involved in the contest.\"\n"
            "— Thomas Paine, Common Sense, January 1776"
        ),
        "questions": [
            {
                "stem": "Paine's argument most directly addressed which obstacle to American independence?",
                "choices": ["The colonists' lack of military experience to defeat British forces",
                            "The reluctance of many colonists to abandon their identity as loyal British subjects",
                            "The failure of colonial legislatures to coordinate a unified military strategy",
                            "The unwillingness of European powers to support an American rebellion"],
                "answer": "B",
                "explanation": "Most colonists in 1775–76 still thought of themselves as Englishmen. Paine reframed the conflict as a universal cause that transcended British identity.",
                "skill": "Sourcing & Situation",
                "reasoning": "Causation",
            },
            {
                "stem": "Paine's framing of the American cause as affecting 'one eighth part of the habitable globe' most directly served which rhetorical purpose?",
                "choices": ["Exaggerating British military strength to generate fear",
                            "Elevating a colonial tax dispute into a universal struggle for human liberty",
                            "Arguing that geographic size made the colonies impossible for Britain to govern",
                            "Appealing to European monarchs for military and financial support"],
                "answer": "B",
                "explanation": "By scaling the conflict to global and historical significance, Paine transformed a dispute about parliamentary taxation into a world-historical cause for liberty—making independence feel inevitable rather than radical.",
                "skill": "Claims & Evidence",
                "reasoning": "Contextualization",
            },
            {
                "stem": "Common Sense was significant primarily because it",
                "choices": ["Provided the legal framework for the Declaration of Independence",
                            "Shifted colonial public opinion toward independence by making the case in plain, accessible language",
                            "Convinced the Continental Congress to declare war on Britain",
                            "Outlined a detailed plan of government for the new nation"],
                "answer": "B",
                "explanation": "Written in direct, accessible prose rather than scholarly Latin or legal jargon, Common Sense reached a mass audience and shifted public opinion in early 1776 when many colonists still hoped for reconciliation.",
                "skill": "Making Connections",
                "reasoning": "Causation",
            },
        ],
    },

    # ── PERIOD 4 ──
    {
        "period": 4,
        "stimulus": (
            "\"We hold these truths to be self-evident: that all men and women are created equal; "
            "that they are endowed by their Creator with certain inalienable rights... The history "
            "of mankind is a history of repeated injuries and usurpations on the part of man toward "
            "woman... He has never permitted her to exercise her inalienable right to the elective "
            "franchise.\"\n"
            "— Declaration of Sentiments, Seneca Falls Convention, 1848"
        ),
        "questions": [
            {
                "stem": "The Declaration of Sentiments most directly drew on which intellectual tradition?",
                "choices": ["The abolitionist movement's argument that all bondage violated natural law",
                            "The republican ideology of the American Revolution grounding rights in natural equality",
                            "The Second Great Awakening's emphasis on moral perfectionism",
                            "European liberal philosophy advocating universal suffrage"],
                "answer": "B",
                "explanation": "The Declaration deliberately echoes the Declaration of Independence—adding 'and women' to force Americans to confront the contradiction between revolutionary principles and women's exclusion.",
                "skill": "Sourcing & Situation",
                "reasoning": "Comparison",
            },
            {
                "stem": "The Seneca Falls Convention was most directly a product of which broader antebellum development?",
                "choices": ["The Market Revolution's displacement of women from productive economic roles",
                            "The reform movements of the 1830s–40s that encouraged women's public activism",
                            "The expansion of public education that gave women access to political philosophy",
                            "The decline of evangelical religion that had previously confined women to domestic roles"],
                "answer": "B",
                "explanation": "Women who participated in temperance, abolition, and moral reform movements developed organizational skills and political consciousness that led them to demand rights for themselves.",
                "skill": "Contextualization",
                "reasoning": "Causation",
            },
            {
                "stem": "The demand for women's suffrage at Seneca Falls was controversial even among attendees because",
                "choices": ["Most women at the convention opposed expanding voting rights beyond property owners",
                            "Demanding the vote seemed too radical and might discredit the broader movement for women's rights",
                            "The Constitution explicitly prohibited women from voting in federal elections",
                            "Frederick Douglass argued that Black male suffrage should take priority"],
                "answer": "B",
                "explanation": "Many attendees supported property rights and legal equality but feared that demanding suffrage—the most radical claim—would alienate potential supporters and undermine the entire movement.",
                "skill": "Claims & Evidence",
                "reasoning": "Contextualization",
            },
        ],
    },

    # ── PERIOD 5 ──
    {
        "period": 5,
        "stimulus": (
            "In August 1862, Lincoln wrote to editor Horace Greeley: 'My paramount object in this "
            "struggle is to save the Union, and is not either to save or to destroy slavery. If I "
            "could save the Union without freeing any slave I would do it, and if I could save it "
            "by freeing all the slaves I would do that.' Six weeks later, Lincoln issued the "
            "preliminary Emancipation Proclamation."
        ),
        "questions": [
            {
                "stem": "The juxtaposition of Lincoln's letter and the Emancipation Proclamation most directly suggests which of the following?",
                "choices": ["Lincoln was personally indifferent to slavery and acted purely for strategic reasons",
                            "Emancipation was a calculated war measure that Lincoln framed to maintain broad political support",
                            "Lincoln's views on slavery changed dramatically in six weeks",
                            "The Emancipation Proclamation was forced on Lincoln by Radical Republicans"],
                "answer": "B",
                "explanation": "Lincoln had already drafted the Proclamation before writing to Greeley. The letter was public-relations, designed to retain Unionists who opposed abolition while he pursued emancipation.",
                "skill": "Sourcing & Situation",
                "reasoning": "Contextualization",
            },
            {
                "stem": "The Emancipation Proclamation's limitation to states 'in rebellion' most directly reveals which political calculation?",
                "choices": ["Lincoln believed Congress lacked authority to abolish slavery anywhere",
                            "Lincoln needed to keep border slave states loyal to the Union",
                            "Lincoln opposed abolition but was pressured by military commanders",
                            "The Proclamation was intended as a bargaining tool to end the war through negotiation"],
                "answer": "B",
                "explanation": "By exempting loyal slave states (Missouri, Kentucky, Maryland, Delaware), Lincoln avoided driving them into the Confederacy while still using emancipation as a war measure under his commander-in-chief powers.",
                "skill": "Claims & Evidence",
                "reasoning": "Causation",
            },
            {
                "stem": "The Emancipation Proclamation most significantly changed the character of the Civil War by",
                "choices": ["Immediately freeing all enslaved people in the United States",
                            "Transforming the war from a fight to preserve the Union into a war for human freedom",
                            "Granting citizenship rights to formerly enslaved people in Union-held territories",
                            "Securing immediate European diplomatic recognition of the Confederacy"],
                "answer": "B",
                "explanation": "After the Proclamation, the war's purpose expanded from Union preservation to include ending slavery—making European intervention on the Confederacy's behalf politically impossible and encouraging Black enlistment.",
                "skill": "Making Connections",
                "reasoning": "Continuity & Change Over Time",
            },
        ],
    },

    # ── PERIOD 6 ──
    {
        "period": 6,
        "stimulus": (
            "\"We meet in the midst of a nation brought to the verge of moral, political, and "
            "material ruin. Corruption dominates the ballot-box, the Legislatures, the Congress... "
            "The newspapers are largely subsidized or muzzled, public opinion silenced, business "
            "prostrated, homes covered with mortgages, labor impoverished, and the land "
            "concentrating in the hands of capitalists.\"\n"
            "— Populist Party Platform, 1892"
        ),
        "questions": [
            {
                "stem": "The Populist platform's critique most directly reflected the grievances of which group?",
                "choices": ["Industrial wage workers seeking an eight-hour workday",
                            "Southern and Western farmers trapped in debt by falling crop prices",
                            "Small business owners threatened by railroad monopolies",
                            "Recent immigrants facing discrimination in Eastern cities"],
                "answer": "B",
                "explanation": "The Populists' core constituency was indebted farmers facing falling prices, high freight rates, and limited credit. Their demands included currency inflation, railroad regulation, and a graduated income tax.",
                "skill": "Sourcing & Situation",
                "reasoning": "Contextualization",
            },
            {
                "stem": "The Populist movement's call for government ownership of railroads most directly represented which ideological challenge?",
                "choices": ["A rejection of capitalism in favor of a socialist economic system",
                            "A demand that government regulate private enterprise to protect ordinary citizens",
                            "An attempt to restore the pre-industrial agrarian economy",
                            "A call for states' rights against federal overreach"],
                "answer": "B",
                "explanation": "Populists were not socialists—they were capitalists who believed the market had been corrupted by monopoly. They demanded government intervention to restore fair competition, not abolish private enterprise.",
                "skill": "Claims & Evidence",
                "reasoning": "Comparison",
            },
            {
                "stem": "The Populist movement ultimately declined because",
                "choices": ["Its platform was too radical for any major party to adopt",
                            "William Jennings Bryan's fusion with the Democrats in 1896 absorbed the movement without achieving its core demands",
                            "The discovery of gold ended the currency debate that had united the movement",
                            "Farmers achieved prosperity through new agricultural technologies"],
                "answer": "B",
                "explanation": "Bryan's 1896 nomination merged Populist and Democratic platforms on silver currency but lost the election. The merger cost Populists their independent identity without winning the presidency or enacting their broader reform agenda.",
                "skill": "Making Connections",
                "reasoning": "Causation",
            },
        ],
    },

    # ── PERIOD 7 ──
    {
        "period": 7,
        "stimulus": (
            "\"I aimed at the public's heart, and by accident I hit it in the stomach.\"\n"
            "— Upton Sinclair, on the impact of The Jungle, 1906\n\n"
            "Congress passed the Pure Food and Drug Act and the Meat Inspection Act within months "
            "of the novel's publication. Sinclair had intended his descriptions of meatpacking "
            "conditions to generate sympathy for exploited immigrant workers; instead, middle-class "
            "readers focused on the contamination of their food."
        ),
        "questions": [
            {
                "stem": "The gap between Sinclair's intention and the legislation's focus most directly illustrates which limitation of Progressive Era reform?",
                "choices": ["Reformers lacked organizational capacity to translate outrage into legislation",
                            "Middle-class reformers were more motivated by consumer protection than by workers' rights",
                            "The muckraking press was controlled by corporate interests",
                            "Progressive reforms prioritized immigrant interests over native-born workers"],
                "answer": "B",
                "explanation": "Middle-class consumers mobilized when they feared contaminated meat; they did not equivalently mobilize for immigrant workers' wages or safety. Reform was easier when it served middle-class interests.",
                "skill": "Claims & Evidence",
                "reasoning": "Causation",
            },
            {
                "stem": "Sinclair's The Jungle is best understood as an example of which Progressive Era strategy?",
                "choices": ["Direct political action through third-party organizing",
                            "Using investigative journalism to expose social problems and build public pressure for reform",
                            "Lobbying corporate leaders to adopt voluntary codes of conduct",
                            "Legal challenges to monopolistic business practices through the courts"],
                "answer": "B",
                "explanation": "Muckrakers like Sinclair, Ida Tarbell, and Lincoln Steffens used detailed investigative reporting to expose corruption and social ills, creating public pressure that forced legislative action.",
                "skill": "Contextualization",
                "reasoning": "Comparison",
            },
            {
                "stem": "The Pure Food and Drug Act of 1906 most directly represented which shift in the role of the federal government?",
                "choices": ["The acceptance that government should regulate private industry to protect public health",
                            "The nationalization of food production to ensure quality standards",
                            "The expansion of federal criminal law to prosecute individual business owners",
                            "The creation of a consumer advocacy agency with enforcement powers"],
                "answer": "A",
                "explanation": "The Act marked a significant expansion of federal regulatory power into an area previously left to states and the market—establishing the principle that the government had a legitimate role in protecting consumers from unsafe products.",
                "skill": "Making Connections",
                "reasoning": "Continuity & Change Over Time",
            },
        ],
    },

    # ── PERIOD 8 ──
    {
        "period": 8,
        "stimulus": (
            "\"You may well ask: 'Why direct action? Why sit-ins, marches and so forth? Isn't "
            "negotiation a better path?' You are quite right in calling for negotiation. Indeed, "
            "this is the very purpose of direct action. Nonviolent direct action seeks to create "
            "such a crisis and foster such a tension that a community which has constantly refused "
            "to negotiate is forced to confront the issue.\"\n"
            "— Martin Luther King Jr., Letter from Birmingham Jail, April 16, 1963"
        ),
        "questions": [
            {
                "stem": "King's argument most directly responds to which critique of the Civil Rights Movement?",
                "choices": ["That civil disobedience was legally equivalent to the laws it protested",
                            "That nonviolent protest was ineffective against a violently oppressive system",
                            "That direct action was unnecessarily provocative and impeded peaceful negotiation",
                            "That the movement's goals were too radical for most Americans to accept"],
                "answer": "C",
                "explanation": "King addresses white moderates who argued demonstrations were provocative. His counter: direct action IS negotiation—it forces a crisis that compels reluctant parties to the table.",
                "skill": "Claims & Evidence",
                "reasoning": "Causation",
            },
            {
                "stem": "King's strategy of nonviolent direct action was most directly designed to",
                "choices": ["Persuade Southern white moderates to voluntarily desegregate",
                            "Force the federal government to act by making the status quo politically untenable",
                            "Build economic boycotts strong enough to bankrupt segregated businesses",
                            "Demonstrate moral superiority over white segregationists"],
                "answer": "B",
                "explanation": "King understood that peaceful demonstrators being beaten on national television would shock Northern opinion and force Washington to intervene—the strategy deliberately sought visible confrontation.",
                "skill": "Contextualization",
                "reasoning": "Causation",
            },
            {
                "stem": "King's Letter from Birmingham Jail is most directly comparable to which earlier American document?",
                "choices": ["The Declaration of Independence's appeal to universal natural rights",
                            "The Federalist Papers' argument for a stronger central government",
                            "Henry David Thoreau's essay on civil disobedience and unjust laws",
                            "Frederick Douglass's 'What to the Slave Is the Fourth of July?' speech"],
                "answer": "C",
                "explanation": "Like Thoreau, King argues that individuals have a moral obligation to disobey unjust laws and accept the consequences. Both documents defend civil disobedience as a higher form of patriotism.",
                "skill": "Making Connections",
                "reasoning": "Comparison",
            },
        ],
    },

    # ── PERIOD 9 ──
    {
        "period": 9,
        "stimulus": (
            "\"Government is not the solution to our problem; government is the problem... "
            "It is time to check and reverse the growth of government, which shows signs of "
            "having grown beyond the consent of the governed.\"\n"
            "— Ronald Reagan, First Inaugural Address, January 20, 1981"
        ),
        "questions": [
            {
                "stem": "Reagan's argument represented a departure from which political consensus that had shaped policy since the New Deal?",
                "choices": ["The belief that free markets required minimal government interference",
                            "The bipartisan acceptance that government had a legitimate role in managing the economy and providing social welfare",
                            "The Cold War consensus that military spending was necessary to contain Soviet expansion",
                            "The progressive tradition that corporate power required regulation to protect workers"],
                "answer": "B",
                "explanation": "Since 1933, both parties had accepted the basic New Deal framework. Even Eisenhower preserved FDR's programs. Reagan's inauguration directly challenged this consensus.",
                "skill": "Sourcing & Situation",
                "reasoning": "Continuity & Change Over Time",
            },
            {
                "stem": "Reagan's election in 1980 was most directly a response to which combination of factors?",
                "choices": ["Rising crime rates and the failure of the War on Drugs",
                            "Economic stagflation, the Iran hostage crisis, and a conservative backlash against 1960s liberalism",
                            "The collapse of the Soviet Union and the end of the Cold War",
                            "Widespread public support for cutting Social Security and Medicare"],
                "answer": "B",
                "explanation": "Reagan's coalition united economic conservatives frustrated by stagflation, religious conservatives alarmed by cultural changes, and foreign policy hawks who saw Carter as weak—a combination that reshaped American politics.",
                "skill": "Contextualization",
                "reasoning": "Causation",
            },
            {
                "stem": "Reagan's conservative revolution most directly parallels which earlier political realignment in American history?",
                "choices": ["The Jacksonian revolution of the 1830s that expanded white male suffrage",
                            "The New Deal realignment of the 1930s that fundamentally redefined the role of government",
                            "The Progressive Era reforms that expanded federal regulatory power",
                            "The post-Civil War Reconstruction that expanded citizenship rights"],
                "answer": "B",
                "explanation": "Both the New Deal and the Reagan Revolution were transformative realignments that fundamentally changed the dominant governing philosophy—FDR expanded government's role; Reagan sought to reverse that expansion.",
                "skill": "Making Connections",
                "reasoning": "Comparison",
            },
        ],
    },
]


# ─── Claude batch generation (1 stimulus → 3 questions) ──────────────────────

def generate_question_set(period_num: int) -> dict | None:
    """Generate one stimulus with 3 questions using Claude + student's PDF notes."""
    period_info = PERIODS[period_num]
    notes = UNIT_NOTES.get(str(period_num), "")
    # Truncate notes to fit in context
    notes_excerpt = notes[:3000] if notes else "No notes available."

    prompt = f"""You are an AP United States History exam question writer for the College Board.

Generate ONE stimulus-based question SET for Period {period_num} ({period_info['range']}: {period_info['name']}).

The set must have: 1 stimulus document + 3 multiple-choice questions about that stimulus.

STUDENT'S STUDY NOTES FOR THIS PERIOD (use these topics/themes):
---
{notes_excerpt}
---

REQUIREMENTS:
1. STIMULUS: Write a realistic primary source excerpt (speech, letter, editorial, testimony) OR a secondary source (historian's argument) OR a data description. 3-6 sentences. Historically accurate.
2. THREE QUESTIONS about that ONE stimulus, each testing a DIFFERENT AP skill:
   - Q1: Sourcing & Situation (author's POV, purpose, audience, historical situation)
   - Q2: Claims & Evidence OR Contextualization (analyzing claims or connecting to broader context)
   - Q3: Making Connections (comparison, causation, or continuity/change across time)
3. Questions must test ANALYSIS not recall. All 4 choices must be plausible.
4. Draw from topics in the student's notes above.
5. Each explanation must say why wrong answers fail, not just why the right one is correct.

EXACT FORMAT (no extra text):

STIMULUS:
[stimulus text — include attribution like "— Author, Source, Date"]

QUESTION 1:
SKILL: [skill name]
REASONING: [Causation/Comparison/Continuity & Change Over Time]
[question stem]
A) [choice]
B) [choice]
C) [choice]
D) [choice]
ANSWER: [letter]
EXPLANATION: [explanation]

QUESTION 2:
SKILL: [skill name]
REASONING: [reasoning]
[question stem]
A) [choice]
B) [choice]
C) [choice]
D) [choice]
ANSWER: [letter]
EXPLANATION: [explanation]

QUESTION 3:
SKILL: [skill name]
REASONING: [reasoning]
[question stem]
A) [choice]
B) [choice]
C) [choice]
D) [choice]
ANSWER: [letter]
EXPLANATION: [explanation]"""

    try:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=3000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            raw = stream.get_final_message()

        text = next(b.text for b in raw.content if b.type == "text")
        return _parse_question_set(text, period_num)
    except Exception as e:
        print(f"Generation error: {e}", file=sys.stderr)
        return None


def _parse_question_set(text: str, period_num: int) -> dict | None:
    """Parse Claude's response into a question set."""
    import re

    try:
        # Extract stimulus
        stim_match = re.search(r"STIMULUS:\s*\n(.*?)(?=\nQUESTION 1:)", text, re.DOTALL)
        if not stim_match:
            return None
        stimulus = stim_match.group(1).strip()

        # Extract questions
        questions = []
        for i in range(1, 4):
            next_q = f"QUESTION {i+1}:" if i < 3 else "$"
            pattern = rf"QUESTION {i}:\s*\n(.*?)(?={next_q})"
            q_match = re.search(pattern, text, re.DOTALL)
            if not q_match:
                continue
            q_block = q_match.group(1).strip()

            # Parse skill/reasoning
            skill_match = re.search(r"SKILL:\s*(.+)", q_block)
            reasoning_match = re.search(r"REASONING:\s*(.+)", q_block)
            skill = skill_match.group(1).strip() if skill_match else "Claims & Evidence"
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "Causation"

            # Parse choices
            choices = []
            for letter in "ABCD":
                c_match = re.search(rf"{letter}\)\s*(.+?)(?=[ABCD]\)|ANSWER:|$)", q_block, re.DOTALL)
                if c_match:
                    choices.append(c_match.group(1).strip())

            # Parse answer
            ans_match = re.search(r"ANSWER:\s*([ABCD])", q_block)
            answer = ans_match.group(1) if ans_match else ""

            # Parse explanation
            exp_match = re.search(r"EXPLANATION:\s*(.*?)$", q_block, re.DOTALL)
            explanation = exp_match.group(1).strip() if exp_match else ""

            # Parse stem (text between REASONING line and A))
            lines = q_block.splitlines()
            stem_lines = []
            capture = False
            for line in lines:
                s = line.strip()
                if s.startswith("REASONING:"):
                    capture = True
                    continue
                if s.startswith("A)"):
                    break
                if capture and s:
                    stem_lines.append(s)
            stem = " ".join(stem_lines)

            if stem and len(choices) == 4 and answer and explanation:
                questions.append({
                    "stem": stem,
                    "choices": choices,
                    "answer": answer,
                    "explanation": explanation,
                    "skill": skill,
                    "reasoning": reasoning,
                })

        if len(questions) < 2:
            return None

        return {
            "period": period_num,
            "stimulus": stimulus,
            "questions": questions,
            "claude_generated": True,
        }
    except Exception:
        return None


# ─── Generate new questions from exam stimuli ────────────────────────────────

def generate_from_exam_stimulus(stim_entry: dict) -> dict | None:
    """Take an existing exam stimulus and generate 3 NEW questions for it using Claude."""
    if not HAS_API_KEY or not client:
        return None

    period_info = PERIODS[stim_entry["period"]]
    stimulus = stim_entry["stimulus"]

    prompt = f"""You are an AP United States History exam question writer.

Below is a STIMULUS from a practice exam. Generate 3 NEW multiple-choice questions for it.
Do NOT recreate the original questions — write completely new ones that test different skills and angles.

PERIOD: {stim_entry['period']} ({period_info['range']}: {period_info['name']})

STIMULUS:
{stimulus}

REQUIREMENTS:
1. Three NEW questions about this stimulus, each testing a DIFFERENT AP skill:
   - Q1: Sourcing & Situation (author's POV, purpose, audience, historical context)
   - Q2: Claims & Evidence OR Contextualization
   - Q3: Making Connections (comparison, causation, or continuity/change across time)
2. Questions must test ANALYSIS not recall. All 4 choices must be plausible.
3. These must be DIFFERENT from typical practice exam questions — go deeper.
4. Each explanation must say why wrong answers fail.

EXACT FORMAT (no extra text):

QUESTION 1:
SKILL: [skill name]
REASONING: [Causation/Comparison/Continuity & Change Over Time]
[question stem]
A) [choice]
B) [choice]
C) [choice]
D) [choice]
ANSWER: [letter]
EXPLANATION: [explanation]

QUESTION 2:
SKILL: [skill name]
REASONING: [reasoning]
[question stem]
A) [choice]
B) [choice]
C) [choice]
D) [choice]
ANSWER: [letter]
EXPLANATION: [explanation]

QUESTION 3:
SKILL: [skill name]
REASONING: [reasoning]
[question stem]
A) [choice]
B) [choice]
C) [choice]
D) [choice]
ANSWER: [letter]
EXPLANATION: [explanation]"""

    try:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=2500,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            raw = stream.get_final_message()

        text = next(b.text for b in raw.content if b.type == "text")
        result = _parse_question_set(f"STIMULUS:\n{stimulus}\n\n{text}", stim_entry["period"])
        if result:
            result["claude_generated"] = True
            result["exam_source"] = stim_entry.get("source", "")
        return result
    except Exception as e:
        print(f"Exam stimulus generation error: {e}", file=sys.stderr)
        return None


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", periods=PERIODS)


@app.route("/api/periods")
def api_periods():
    return jsonify(PERIODS)


@app.route("/api/prewritten", methods=["POST"])
def api_prewritten():
    """Get pre-written question sets for selected periods."""
    data = request.json
    selected = data.get("periods", [])
    count = data.get("count", 3)

    candidates = [s for s in PREWRITTEN_SETS if s["period"] in selected]
    random.shuffle(candidates)
    result = candidates[:count]

    for s in result:
        s["claude_generated"] = False

    return jsonify(result)


@app.route("/api/exam_stimuli_count", methods=["POST"])
def api_exam_stimuli_count():
    """Return count of available exam stimuli for selected periods."""
    data = request.json
    selected = data.get("periods", [])
    count = sum(1 for s in EXAM_STIMULI if s["period"] in selected and len(s["stimulus"]) > 80)
    return jsonify({"count": count})


@app.route("/api/has_api_key")
def api_has_key():
    return jsonify({"has_key": HAS_API_KEY})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Generate a Claude question set for a given period."""
    if not HAS_API_KEY:
        return jsonify({"error": "No ANTHROPIC_API_KEY set. Claude generation is disabled."}), 400

    data = request.json
    period = data.get("period", 1)

    result = generate_question_set(period)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate questions"}), 500


@app.route("/api/generate_from_exam", methods=["POST"])
def api_generate_from_exam():
    """Generate new questions from an existing exam stimulus."""
    if not HAS_API_KEY:
        return jsonify({"error": "No ANTHROPIC_API_KEY set."}), 400

    data = request.json
    period = data.get("period", 1)

    # Pick a random exam stimulus for this period
    candidates = [s for s in EXAM_STIMULI if s["period"] == period and len(s["stimulus"]) > 80]
    if not candidates:
        return jsonify({"error": f"No exam stimuli available for period {period}"}), 404

    chosen = random.choice(candidates)
    result = generate_from_exam_stimulus(chosen)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate questions from exam stimulus"}), 500


@app.route("/api/hstp_stimuli_count", methods=["POST"])
def api_hstp_stimuli_count():
    """Return count of available HSTP stimuli for selected periods."""
    data = request.json
    selected = data.get("periods", [])
    count = sum(1 for s in HSTP_STIMULI if s["period"] in selected)
    return jsonify({"count": count})


@app.route("/api/generate_from_hstp", methods=["POST"])
def api_generate_from_hstp():
    """Generate new questions from a highschooltestprep.com stimulus."""
    if not HAS_API_KEY:
        return jsonify({"error": "No ANTHROPIC_API_KEY set."}), 400

    data = request.json
    period = data.get("period", 1)

    candidates = [s for s in HSTP_STIMULI if s["period"] == period]
    if not candidates:
        return jsonify({"error": f"No HSTP stimuli available for period {period}"}), 404

    chosen = random.choice(candidates)
    result = generate_from_exam_stimulus(chosen)
    if result:
        result["exam_source"] = "hstp"
        return jsonify(result)
    return jsonify({"error": "Failed to generate questions from HSTP stimulus"}), 500


def generate_saq(period_num: int) -> dict | None:
    """Generate a Short Answer Question for a given period."""
    if not HAS_API_KEY or not client:
        return None

    period_info = PERIODS[period_num]

    notes_context = ""
    for key, text in UNIT_NOTES.items():
        if str(period_num) in key:
            notes_context += text[:2000]

    prompt = f"""You are an AP United States History exam question writer.

Generate a Short Answer Question (SAQ) for Period {period_num} ({period_info['range']}: {period_info['name']}).

AP SAQ format:
- A stimulus: primary source excerpt OR historian's argument (2-4 sentences)
- 3 parts (a, b, c), each worth exactly 1 point
- Part A: "Briefly describe" or "Briefly explain" ONE thing directly from/supported by the stimulus
- Part B: "Briefly explain" ONE historical development, cause, or effect from the period
- Part C: "Briefly explain" ONE comparison, contrast, or continuity/change over time

{'CONTEXT FROM STUDENT NOTES:' + notes_context[:1500] if notes_context else ''}

EXACT FORMAT (no extra text before or after):

STIMULUS:
[2-4 sentence primary source excerpt or historian argument]

SOURCE: [Author, Title, Date]

PART_A:
[Part A question — say "Briefly describe" or "Briefly explain" ONE specific thing from the stimulus]

PART_B:
[Part B question — say "Briefly explain" ONE cause/effect/development]

PART_C:
[Part C question — say "Briefly explain" ONE comparison, contrast, or continuity/change]"""

    try:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1500,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            raw = stream.get_final_message()

        text = next(b.text for b in raw.content if b.type == "text")
        return _parse_saq(text, period_num)
    except Exception as e:
        print(f"SAQ generation error: {e}", file=sys.stderr)
        return None


def _parse_saq(text: str, period_num: int) -> dict | None:
    """Parse Claude's SAQ output into structured data."""
    import re
    stimulus_m = re.search(r'STIMULUS:\s*\n(.*?)(?=\nSOURCE:|\nPART_A:)', text, re.DOTALL)
    source_m   = re.search(r'SOURCE:\s*(.*?)(?=\nPART_A:)', text, re.DOTALL)
    part_a_m   = re.search(r'PART_A:\s*\n(.*?)(?=\nPART_B:)', text, re.DOTALL)
    part_b_m   = re.search(r'PART_B:\s*\n(.*?)(?=\nPART_C:)', text, re.DOTALL)
    part_c_m   = re.search(r'PART_C:\s*\n(.*?)$', text, re.DOTALL)
    if not all([stimulus_m, part_a_m, part_b_m, part_c_m]):
        return None
    return {
        "period": period_num,
        "stimulus": stimulus_m.group(1).strip(),
        "source": source_m.group(1).strip() if source_m else "",
        "parts": [
            {"label": "A", "question": part_a_m.group(1).strip()},
            {"label": "B", "question": part_b_m.group(1).strip()},
            {"label": "C", "question": part_c_m.group(1).strip()},
        ]
    }


def grade_saq(saq_data: dict, responses: dict) -> dict | None:
    """Grade SAQ responses using Claude."""
    if not HAS_API_KEY or not client:
        return None

    parts = saq_data["parts"]

    prompt = f"""You are an AP US History SAQ grader. Grade each part 0 or 1.

A response earns 1 point if it directly addresses the question with accurate historical evidence or reasoning.
A response earns 0 points if it is blank, off-topic, historically inaccurate, or only restates the question.

STIMULUS:
{saq_data['stimulus']}
{('SOURCE: ' + saq_data['source']) if saq_data.get('source') else ''}

PART A: {parts[0]['question']}
PART B: {parts[1]['question']}
PART C: {parts[2]['question']}

STUDENT RESPONSES:
Part A: {responses.get('a', '[No response]') or '[No response]'}
Part B: {responses.get('b', '[No response]') or '[No response]'}
Part C: {responses.get('c', '[No response]') or '[No response]'}

EXACT FORMAT:

PART_A_SCORE: [0 or 1]
PART_A_FEEDBACK: [2-3 sentences: explain the score and what a full-credit response needs]

PART_B_SCORE: [0 or 1]
PART_B_FEEDBACK: [2-3 sentences]

PART_C_SCORE: [0 or 1]
PART_C_FEEDBACK: [2-3 sentences]

TOTAL: [0, 1, 2, or 3]
OVERALL: [1-2 sentences of holistic feedback]"""

    try:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1200,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            raw = stream.get_final_message()

        text = next(b.text for b in raw.content if b.type == "text")
        return _parse_saq_grade(text)
    except Exception as e:
        print(f"SAQ grading error: {e}", file=sys.stderr)
        return None


def _parse_saq_grade(text: str) -> dict | None:
    import re

    def get_score(label):
        m = re.search(rf'PART_{label}_SCORE:\s*([01])', text)
        return int(m.group(1)) if m else 0

    def get_feedback(label):
        m = re.search(rf'PART_{label}_FEEDBACK:\s*(.*?)(?=\nPART_[BC]_SCORE:|\nTOTAL:|\Z)', text, re.DOTALL)
        return m.group(1).strip() if m else ""

    total_m   = re.search(r'TOTAL:\s*([0-3])', text)
    overall_m = re.search(r'OVERALL:\s*(.*?)$', text, re.DOTALL)

    return {
        "parts": {
            "a": {"score": get_score('A'), "feedback": get_feedback('A')},
            "b": {"score": get_score('B'), "feedback": get_feedback('B')},
            "c": {"score": get_score('C'), "feedback": get_feedback('C')},
        },
        "total": int(total_m.group(1)) if total_m else (get_score('A') + get_score('B') + get_score('C')),
        "overall": overall_m.group(1).strip() if overall_m else "",
    }


@app.route("/api/generate_saq", methods=["POST"])
def api_generate_saq():
    if not HAS_API_KEY:
        return jsonify({"error": "No ANTHROPIC_API_KEY set."}), 400
    data = request.json
    period = data.get("period", 1)
    result = generate_saq(period)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate SAQ"}), 500


@app.route("/api/grade_saq", methods=["POST"])
def api_grade_saq():
    if not HAS_API_KEY:
        return jsonify({"error": "No ANTHROPIC_API_KEY set."}), 400
    data = request.json
    saq_data  = data.get("saq")
    responses = data.get("responses", {})
    if not saq_data:
        return jsonify({"error": "No SAQ data provided"}), 400
    result = grade_saq(saq_data, responses)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to grade SAQ"}), 500


if __name__ == "__main__":
    exam_count = len([s for s in EXAM_STIMULI if len(s["stimulus"]) > 80])
    hstp_count = len(HSTP_STIMULI)
    print(f"\n  APUSH MCQ Practice Tool")
    print(f"  {len(PREWRITTEN_SETS)} pre-written sets + {exam_count} exam stimuli + {hstp_count} HSTP stimuli loaded")
    if not HAS_API_KEY:
        print("  NOTE: No ANTHROPIC_API_KEY set — Claude generation disabled.")
        print("  Pre-written questions will still work. Set the env var to enable Claude.\n")
    print("  Open http://localhost:5050 in your browser\n")
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=False, host="0.0.0.0", port=port)
