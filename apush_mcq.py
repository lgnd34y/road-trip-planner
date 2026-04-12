#!/usr/bin/env python3
"""
APUSH MCQ Practice Tool
- All questions are stimulus-based (matching the redesigned AP exam format)
- ~5 pre-written questions per period (45 total), College Board style
- Claude generates batches of 3 harder questions per API call
- AP skill category + historical reasoning process labeled on every question
"""

import os
import sys
import random
import textwrap
import anthropic

client = anthropic.Anthropic()

# ─── Color helpers ─────────────────────────────────────────────────────────────
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
DIM    = "\033[2m"

def bold(s):   return f"{BOLD}{s}{RESET}"
def cyan(s):   return f"{CYAN}{s}{RESET}"
def green(s):  return f"{GREEN}{s}{RESET}"
def red(s):    return f"{RED}{s}{RESET}"
def yellow(s): return f"{YELLOW}{s}{RESET}"
def blue(s):   return f"{BLUE}{s}{RESET}"
def dim(s):    return f"{DIM}{s}{RESET}"

# ─── AP Skill & Reasoning metadata ────────────────────────────────────────────
# Historical Reasoning Processes
HRP_CAUSATION    = "Causation"
HRP_COMPARISON   = "Comparison"
HRP_CCOT         = "Continuity & Change Over Time"
HRP_CONTEXT      = "Contextualization"

# AP Exam Skills
SKILL_SOURCING   = "Sourcing & Situation"
SKILL_CLAIMS     = "Claims & Evidence"
SKILL_CONTEXT    = "Contextualization"
SKILL_CONNECT    = "Making Connections"
SKILL_ARGUMENT   = "Argumentation"

# ─── Period metadata ───────────────────────────────────────────────────────────
PERIODS = {
    1: ("1491–1607", "Pre-Columbian Americas & Early European Contact"),
    2: ("1607–1754", "Colonial America"),
    3: ("1754–1800", "Revolution & the Early Republic"),
    4: ("1800–1848", "Jacksonian Democracy & Manifest Destiny"),
    5: ("1844–1877", "Civil War Era & Reconstruction"),
    6: ("1865–1898", "Gilded Age & Industrialization"),
    7: ("1890–1945", "Progressive Era, WWI, Depression & WWII"),
    8: ("1945–1980", "Cold War, Civil Rights & Vietnam"),
    9: ("1980–Present", "Reagan Era to Today"),
}

# ─── Pre-written stimulus-based questions ─────────────────────────────────────
# All questions include a stimulus, matching the redesigned AP exam (2015+).
# Fields: period, stimulus, stem, choices [A,B,C,D], answer, explanation,
#         skill, reasoning
PREWRITTEN = [

    # ── PERIOD 1: 1491–1607 ──────────────────────────────────────────────────
    {
        "period": 1,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "Archaeological evidence from Cahokia (near present-day St. Louis) reveals a city "
            "that at its peak around 1100 CE housed an estimated 10,000–20,000 people, making it "
            "larger than contemporary London. The site features massive earthen mounds, a central "
            "plaza, and evidence of long-distance trade in copper, mica, and shells. The city "
            "declined sharply after 1200 CE, likely due to environmental degradation and political instability."
        ),
        "stem": (
            "The archaeological evidence from Cahokia most directly challenges which common assumption "
            "about pre-Columbian North America?"
        ),
        "choices": [
            "That Native Americans engaged in long-distance trade networks",
            "That complex, densely populated urban societies did not exist north of Mexico",
            "That environmental factors played no role in the collapse of Native civilizations",
            "That Mississippian culture was largely isolated from Mesoamerican influence",
        ],
        "answer": "B",
        "explanation": (
            "Cahokia's scale—rivaling major European cities of its era—directly contradicts the "
            "common assumption that sophisticated urban civilization in the Americas was confined to "
            "Mesoamerica and South America. The evidence of long-distance trade (A) actually confirms, "
            "not challenges, what is already known about Native trade. Environmental decline (C) is "
            "explicitly mentioned. Mesoamerican influence (D) is a debated but separate scholarly question."
        ),
    },
    {
        "period": 1,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"They brought us parrots and balls of cotton and spears and many other things, which "
            "they exchanged for the glass beads and hawks' bells. They willingly traded everything "
            "they owned... They do not bear arms, and do not know them, for I showed them a sword, "
            "they took it by the edge and cut themselves out of ignorance... They would make fine "
            "servants... with fifty men we could subjugate them all and make them do whatever we want.\""
            " — Christopher Columbus, Journal, October 1492"
        ),
        "stem": (
            "Columbus's observations most directly reflect which of the following motivations shaping "
            "early Spanish colonial policy in the Americas?"
        ),
        "choices": [
            "A desire to establish peaceful commercial partnerships with indigenous peoples",
            "The belief that Native peoples were culturally sophisticated equals who required diplomacy",
            "The drive to exploit indigenous labor and resources for Spanish imperial profit",
            "A commitment to Christian missionary work as the primary goal of colonization",
        ],
        "answer": "C",
        "explanation": (
            "Columbus immediately assesses Native peoples in terms of their exploitability—noting their "
            "lack of weapons and imagining 'fifty men' could subjugate them. This extractive mindset "
            "directly foreshadowed the encomienda system. While missionary work (D) was part of Spanish "
            "colonization, Columbus's language here prioritizes labor and subjugation over conversion."
        ),
    },
    {
        "period": 1,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "Historians have noted that Spanish, French, and English colonizers pursued fundamentally "
            "different strategies in the Americas. The Spanish focused on conquest and extraction of "
            "mineral wealth using indigenous and enslaved labor. The French prioritized fur trade "
            "alliances with Native peoples, avoiding large permanent settlements. The English sought "
            "to establish permanent agricultural settlements, which required displacing Native populations "
            "from the land."
        ),
        "stem": (
            "Which of the following best explains why French colonizers were generally more successful "
            "than the English in maintaining long-term alliances with Native American nations?"
        ),
        "choices": [
            "France had a stronger military capable of enforcing treaty obligations",
            "The French fur trade model created economic interdependence without requiring Native land displacement",
            "French missionaries were more effective at converting Native peoples to Christianity",
            "Native Americans preferred French trade goods to English manufactured goods",
        ],
        "answer": "B",
        "explanation": (
            "French colonization depended on Native participation in the fur trade—Native hunters "
            "and knowledge were essential, not obstacles. This created mutual economic benefit without "
            "the land pressure that made English-Native relations so violent. Military strength (A) "
            "and missionary success (C) were not decisive factors. Trade goods preference (D) is a "
            "superficial explanation that misses the structural difference in colonial models."
        ),
    },
    {
        "period": 1,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"The encomenderos treat the Indians worse than slaves... They demand tribute in gold "
            "even from those who possess none. When the Indians cannot pay, they take their children "
            "as payment. Villages are emptied, families destroyed. I have witnessed massacres committed "
            "not out of necessity but from pure cruelty and greed. Is it not clear that such acts "
            "destroy not only the bodies of these people but the souls of those who commit them?\""
            " — Bartolomé de las Casas, A Short Account of the Destruction of the Indies, 1542"
        ),
        "stem": (
            "Las Casas's account is most useful to historians as evidence of which of the following?"
        ),
        "choices": [
            "The universal opposition among Spanish colonists to the encomienda system",
            "The existence of a Spanish moral debate about the treatment of indigenous peoples",
            "The effectiveness of Spanish laws protecting Native Americans from abuse",
            "The success of indigenous resistance movements against Spanish colonial authority",
        ],
        "answer": "B",
        "explanation": (
            "Las Casas represents a segment of Spanish Catholic opinion that condemned colonial "
            "violence on moral and religious grounds—demonstrating that debate existed within Spanish "
            "society about colonial methods. His account cannot tell us about universal Spanish "
            "opposition (A, which was far from universal), the effectiveness of protective laws (C, "
            "which largely failed), or indigenous resistance (D, which is not the subject of his account)."
        ),
    },
    {
        "period": 1,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_CCOT,
        "stimulus": (
            "Scholars estimate that between 1492 and 1650, the indigenous population of the Americas "
            "declined from roughly 50–60 million to fewer than 6 million. Disease accounted for the "
            "majority of deaths, though violence, forced labor, and famine contributed significantly. "
            "This demographic collapse reshaped ecosystems as previously farmed land returned to "
            "forest, reduced labor supplies that drove the Atlantic slave trade, and created the "
            "population vacuum that European colonists would fill."
        ),
        "stem": (
            "The demographic collapse described above most directly contributed to which long-term "
            "development in the Atlantic world?"
        ),
        "choices": [
            "The expansion of European missionary activity into North America",
            "The growth of the transatlantic slave trade as a substitute labor source",
            "The decline of mercantilism as the dominant European economic theory",
            "The development of democratic political institutions in Spanish colonies",
        ],
        "answer": "B",
        "explanation": (
            "The catastrophic decline of Native American populations eliminated the primary labor "
            "force that Spanish colonizers had intended to exploit. This drove the massive expansion "
            "of the African slave trade to supply labor for mines and plantations. Missionary activity "
            "(A) increased but was not the most direct consequence. Mercantilism (C) remained dominant. "
            "Democratic institutions (D) did not develop in Spanish colonies."
        ),
    },

    # ── PERIOD 2: 1607–1754 ──────────────────────────────────────────────────
    {
        "period": 2,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"We appeal to all free men: that the poverty of Virginia is caused not by the "
            "Indians but by those great men who oppress us, who have monopolized the best lands, "
            "who give the governor his commands, and who send their servants armed against us when "
            "we dare to protest. We demand that our servants who have completed their indentures "
            "receive the land they were promised, and that the Indian frontier be opened for "
            "settlement by freemen who have nothing.\""
            " — Nathaniel Bacon, Declaration of the People, 1676 (paraphrased)"
        ),
        "stem": (
            "Bacon's Rebellion (1676) most directly revealed which underlying tension in Chesapeake "
            "colonial society?"
        ),
        "choices": [
            "Religious conflict between Anglican settlers and dissenting Puritan communities",
            "Economic and political grievances of landless freedmen against the planter elite",
            "Resistance among indentured servants to the extension of their service contracts",
            "Conflict between tobacco planters and merchants over control of the export trade",
        ],
        "answer": "B",
        "explanation": (
            "Bacon's coalition included freed indentured servants who had completed their contracts "
            "but found good land monopolized by large planters and the frontier closed. The rebellion "
            "exposed the dangerous instability of a labor system that produced a class of armed, "
            "landless, and resentful freedmen—a key factor driving planters toward enslaved African "
            "labor as a more controllable workforce."
        ),
    },
    {
        "period": 2,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CCOT,
        "stimulus": (
            "Between 1650 and 1750, the proportion of bound laborers in the Chesapeake colonies who "
            "were enslaved Africans rose from roughly 5% to over 60%. Simultaneously, the use of "
            "indentured servitude declined sharply. Historians have attributed this shift to several "
            "factors: declining English emigration, the falling cost of enslaved Africans as the "
            "Royal African Company's monopoly ended, and the appeal of a permanent, hereditary "
            "labor force that could not petition for freedom."
        ),
        "stem": (
            "The shift in Chesapeake labor described above most directly resulted in which of the "
            "following long-term consequences?"
        ),
        "choices": [
            "The development of a more democratic political system as land became more widely available",
            "The entrenchment of a racially based slave society that shaped Southern culture for centuries",
            "The decline of tobacco as the dominant export crop in the Chesapeake region",
            "Increased tension between English colonists and the Crown over taxation of the slave trade",
        ],
        "answer": "B",
        "explanation": (
            "The demographic and economic shift toward African chattel slavery fundamentally transformed "
            "the Chesapeake into a society built on racial hierarchy. As slavery became hereditary and "
            "race-based, it created legal, social, and cultural structures that persisted through "
            "Reconstruction and beyond. Greater land availability (A) did not follow—planters "
            "consolidated holdings. Tobacco (C) remained dominant. Taxation disputes (D) were not "
            "a primary consequence of this specific shift."
        ),
    },
    {
        "period": 2,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"Brethren, you are by nature children of wrath. Your hearts are corrupt, deceitful "
            "above all things. Yet I tell you that God in His infinite mercy has chosen some among "
            "you—not because of your worthiness, but by His sovereign grace alone—to receive the "
            "gift of new birth. Have you felt that stirring within you? That burning conviction of "
            "sin? That is the beginning of grace. Do not trust in your church membership or your "
            "moral conduct—trust only in that direct experience of God's transforming power.\""
            " — George Whitefield, sermon, Philadelphia, 1740 (paraphrased)"
        ),
        "stem": (
            "Whitefield's preaching most directly contributed to which of the following social "
            "developments in colonial America?"
        ),
        "choices": [
            "The consolidation of church authority as congregations rallied around established ministers",
            "The weakening of traditional religious hierarchies as individuals claimed direct spiritual authority",
            "The decline of Calvinist theology in favor of Arminian doctrines emphasizing free will",
            "The unification of colonial denominations into a single American Protestant church",
        ],
        "answer": "B",
        "explanation": (
            "Whitefield and other Great Awakening revivalists bypassed established church structures, "
            "preaching that individual conversion experience—not church membership or clergy approval—"
            "was the measure of true faith. This democratized religious authority and emboldened "
            "laypeople to question established ministers, contributing to church schisms and, some "
            "historians argue, a broader culture of challenging authority that influenced revolutionary thinking."
        ),
    },
    {
        "period": 2,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "New England colonies were founded primarily by Puritan families seeking religious "
            "community, which encouraged the growth of towns, public education, and a relatively "
            "equal distribution of land in small farms. The Chesapeake colonies were founded as "
            "commercial ventures attracting single young men seeking economic opportunity, producing "
            "a dispersed plantation economy, high mortality, and a male-dominated, hierarchical "
            "social structure. The Middle Colonies blended both patterns with diverse ethnic and "
            "religious populations engaged in mixed farming and trade."
        ),
        "stem": (
            "The regional differences described above most directly affected which aspect of "
            "colonial political development?"
        ),
        "choices": [
            "The degree to which each region participated in the Atlantic trade network",
            "The forms of self-governance and political culture that emerged in each region",
            "The pace at which each region developed a market economy",
            "The extent to which each region relied on enslaved labor",
        ],
        "answer": "B",
        "explanation": (
            "New England's town-meeting culture fostered direct democratic participation; Chesapeake's "
            "dispersed plantations and hierarchical society produced an oligarchic planter-dominated "
            "politics; the Middle Colonies' diversity encouraged negotiation and coalition-building. "
            "These distinct political cultures shaped each region's response to imperial authority "
            "and ultimately influenced the debates at the Constitutional Convention."
        ),
    },
    {
        "period": 2,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "During the period of 'salutary neglect' (roughly 1715–1763), the British government "
            "largely refrained from strictly enforcing the Navigation Acts and allowed colonial "
            "assemblies to control their own taxation and spending. Colonial merchants routinely "
            "traded with non-British Caribbean islands in violation of trade laws. When Britain "
            "reversed this policy after 1763 and began enforcing mercantile regulations, colonial "
            "resistance was swift and intense."
        ),
        "stem": (
            "The colonial reaction to British policy after 1763 is best explained by which of "
            "the following arguments?"
        ),
        "choices": [
            "Colonists had always opposed British taxation on ideological grounds derived from Enlightenment philosophy",
            "Decades of self-governance had created expectations of autonomy that stricter imperial control now threatened",
            "The cost of the French and Indian War had left colonists economically unable to pay new taxes",
            "Colonial merchants feared that British regulations would end their profitable Atlantic trade",
        ],
        "answer": "B",
        "explanation": (
            "Salutary neglect had produced generations of effective self-rule. Colonists had come to "
            "treat local control over taxation and trade as customary rights, not privileges. When "
            "Britain tried to reassert authority, colonists experienced it as a novel tyranny rather "
            "than the restoration of existing law. While Enlightenment ideas (A) provided language "
            "for resistance, the lived experience of autonomy is what made abstract principles feel urgent."
        ),
    },

    # ── PERIOD 3: 1754–1800 ──────────────────────────────────────────────────
    {
        "period": 3,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"The sun never shined on a cause of greater worth. 'Tis not the affair of a city, "
            "a country, a province, or a kingdom, but of a continent—of at least one eighth part "
            "of the habitable globe. 'Tis not the concern of a day, a year, or an age; posterity "
            "are virtually involved in the contest, and will be more or less affected, even to the "
            "end of time, by the proceedings now.\""
            " — Thomas Paine, Common Sense, January 1776"
        ),
        "stem": (
            "Paine's argument in Common Sense most directly addressed which obstacle to American independence?"
        ),
        "choices": [
            "The colonists' lack of military experience needed to defeat British forces",
            "The reluctance of many colonists to abandon their identity as loyal British subjects",
            "The failure of colonial legislatures to coordinate a unified military strategy",
            "The unwillingness of European powers to support an American rebellion",
        ],
        "answer": "B",
        "explanation": (
            "Most colonists in 1775–76 still thought of themselves as Englishmen defending their "
            "rights under the British constitution—not as a separate nation seeking independence. "
            "Paine's genius was reframing the conflict not as a dispute about taxation but as a "
            "universal cause that transcended British identity. By urging colonists to see "
            "themselves as citizens of a continent with a world-historical mission, he helped "
            "shift public opinion toward separation."
        ),
    },
    {
        "period": 3,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "\"The powers delegated by the proposed Constitution to the federal government are few "
            "and defined. Those which are to remain in the State governments are numerous and "
            "indefinite... The powers reserved to the several States will extend to all the objects "
            "which, in the ordinary course of affairs, concern the lives, liberties, and properties "
            "of the people.\""
            " — James Madison, Federalist No. 45, 1788"
        ),
        "stem": (
            "Madison's argument in Federalist No. 45 most directly responds to which Anti-Federalist concern?"
        ),
        "choices": [
            "That the new Constitution lacked a Bill of Rights to protect individual liberties",
            "That the federal government would consolidate too much power at the expense of the states",
            "That the presidency would become a monarchy due to the lack of term limits",
            "That the Senate would give small states disproportionate power over legislation",
        ],
        "answer": "B",
        "explanation": (
            "Anti-Federalists like Brutus and the Federal Farmer argued that the Constitution's "
            "broad grants of federal power—especially the Necessary and Proper Clause—would gradually "
            "swallow state authority. Madison directly counters this by arguing that federal powers "
            "are specifically enumerated and limited, while states retain general governance over "
            "everyday life. The Bill of Rights (A) was a separate concern addressed in other essays."
        ),
    },
    {
        "period": 3,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "In the winter of 1786–87, Massachusetts farmers who had fallen into debt following "
            "the Revolution took up arms under Daniel Shays and shut down county courthouses to "
            "prevent foreclosure proceedings. The state militia eventually suppressed the rebellion, "
            "but the episode alarmed national leaders. George Washington wrote, 'Good God! Who "
            "besides a Tory could have foreseen, or a Briton predicted [such a thing]?' The following "
            "summer, delegates gathered in Philadelphia to revise the Articles of Confederation."
        ),
        "stem": (
            "Shays' Rebellion most directly contributed to which political development?"
        ),
        "choices": [
            "A wave of debtor-relief legislation passed by state legislatures across New England",
            "Renewed support among nationalists for drafting a stronger federal constitution",
            "A military alliance between the United States and France to stabilize the new republic",
            "The adoption of the Bill of Rights as the first act of the new Congress",
        ],
        "answer": "B",
        "explanation": (
            "Shays' Rebellion demonstrated to nationalists like Madison, Hamilton, and Washington "
            "that the Articles of Confederation left the central government powerless to maintain "
            "order and protect property. It provided the political urgency that moved reluctant "
            "states to send delegates to Philadelphia and that encouraged those delegates to create "
            "a substantially more powerful federal government than most had initially envisioned."
        ),
    },
    {
        "period": 3,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"The great rule of conduct for us in regard to foreign nations is, in extending our "
            "commercial relations, to have with them as little political connection as possible... "
            "It is our true policy to steer clear of permanent alliances with any portion of the "
            "foreign world... Taking care always to keep ourselves by suitable establishments on a "
            "respectable defensive posture, we may safely trust to temporary alliances for "
            "extraordinary emergencies.\""
            " — George Washington, Farewell Address, 1796"
        ),
        "stem": (
            "Washington's Farewell Address was most directly a response to which political controversy "
            "of the 1790s?"
        ),
        "choices": [
            "The debate over ratifying Jay's Treaty with Britain and deepening ties with a European power",
            "The constitutional debate over whether the president could conduct foreign policy independently",
            "The formation of the Democratic-Republican Party and its criticism of Federalist economic policy",
            "The military threat posed by the French Revolution's spread across Europe",
        ],
        "answer": "A",
        "explanation": (
            "Jay's Treaty (1795) had deeply divided Americans, with Democratic-Republicans arguing "
            "it dangerously tied the United States to Britain at the expense of the French alliance. "
            "Washington's warning against 'permanent alliances' was a direct response to this "
            "partisan foreign policy debate and an effort to prevent future administrations from "
            "being dragged into European conflicts by treaty obligations."
        ),
    },
    {
        "period": 3,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_CCOT,
        "stimulus": (
            "Between 1776 and 1804, Northern states gradually abolished slavery through a combination "
            "of immediate and gradual emancipation laws. During the same period, the Constitutional "
            "Convention protected slavery through the Three-Fifths Compromise, the fugitive slave "
            "clause, and a twenty-year moratorium on banning the slave trade. Simultaneously, "
            "revolutionary rhetoric celebrating liberty and natural rights spread throughout "
            "the Atlantic world, inspiring the Haitian Revolution of 1791."
        ),
        "stem": (
            "The developments described above best illustrate which of the following tensions in "
            "the early American republic?"
        ),
        "choices": [
            "The conflict between Federalist economic nationalism and Jeffersonian agrarianism",
            "The contradiction between the nation's founding ideals of liberty and the political entrenchment of slavery",
            "The tension between state sovereignty and federal authority over domestic institutions",
            "The disagreement between Northern merchants and Southern planters over tariff policy",
        ],
        "answer": "B",
        "explanation": (
            "The founding era simultaneously produced the world's most celebrated statement of "
            "natural rights ('all men are created equal') and a constitution that explicitly "
            "protected human bondage. Northern emancipation showed abolition was possible; "
            "constitutional compromises showed slaveholders' political power; the Haitian "
            "Revolution showed the global stakes. This contradiction—not resolved until 1865—"
            "is the defining tension of the early republic."
        ),
    },

    # ── PERIOD 4: 1800–1848 ──────────────────────────────────────────────────
    {
        "period": 4,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "In 1820, Congress faced a crisis when Missouri applied for statehood as a slave state, "
            "which would upset the balance of eleven free and eleven slave states in the Senate. "
            "After months of debate, Henry Clay brokered the Missouri Compromise: Missouri entered "
            "as a slave state, Maine entered as a free state, and slavery was banned in the "
            "Louisiana Territory north of latitude 36°30'. Thomas Jefferson wrote privately that "
            "the crisis 'like a fire bell in the night, awakened and filled me with terror.'"
        ),
        "stem": (
            "Jefferson's reaction to the Missouri Crisis most directly reflected his concern that"
        ),
        "choices": [
            "The compromise gave too much power to Northern free states at the expense of Southern interests",
            "The sectional division over slavery threatened to destroy the union he had helped create",
            "Congress was asserting an unconstitutional authority to regulate slavery in the territories",
            "The admission of Missouri would accelerate the westward expansion of the plantation system",
        ],
        "answer": "B",
        "explanation": (
            "Jefferson feared that drawing a permanent geographic line between free and slave "
            "territory would solidify sectional identities and make compromise impossible over time. "
            "His 'fire bell in the night' metaphor expressed dread that the union itself was in "
            "mortal danger—not from external enemies but from internal division over slavery. "
            "He had hoped the issue would gradually resolve itself; the Missouri Crisis suggested it would not."
        ),
    },
    {
        "period": 4,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"We hold these truths to be self-evident: that all men and women are created equal; "
            "that they are endowed by their Creator with certain inalienable rights... The history "
            "of mankind is a history of repeated injuries and usurpations on the part of man toward "
            "woman, having in direct object the establishment of an absolute tyranny over her... "
            "He has never permitted her to exercise her inalienable right to the elective franchise.\""
            " — Declaration of Sentiments, Seneca Falls Convention, 1848"
        ),
        "stem": (
            "The Declaration of Sentiments most directly drew on which intellectual tradition to "
            "make its argument for women's rights?"
        ),
        "choices": [
            "The abolitionist movement's argument that all forms of human bondage violated natural law",
            "The republican ideology of the American Revolution, which grounded rights in natural equality",
            "The Second Great Awakening's emphasis on moral perfectionism and individual reform",
            "European liberal philosophy advocating for universal suffrage regardless of sex",
        ],
        "answer": "B",
        "explanation": (
            "The Declaration of Sentiments deliberately echoes the Declaration of Independence—"
            "adding 'and women' to 'all men are created equal' and listing grievances in the "
            "same format. By invoking the language of the founding, Stanton and the Seneca Falls "
            "delegates forced Americans to confront the contradiction between revolutionary principles "
            "and the exclusion of women from political life. While reform movements and abolitionism "
            "influenced the participants, the rhetorical strategy is grounded in Revolutionary republicanism."
        ),
    },
    {
        "period": 4,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "Between 1820 and 1850, the United States built over 3,000 miles of canals and began "
            "constructing a national railroad network. Agricultural output surged as Western farms "
            "gained access to Eastern markets. Factory towns like Lowell, Massachusetts grew "
            "rapidly, employing thousands of young women from New England farm families. Urban "
            "populations swelled as migrants from rural areas and immigrants from Ireland and "
            "Germany sought wage labor."
        ),
        "stem": (
            "The developments described above most directly contributed to which of the following "
            "social changes in antebellum America?"
        ),
        "choices": [
            "A decline in the influence of evangelical Protestantism as secular values spread",
            "The growth of a distinctive working-class identity and early labor organizing",
            "Greater political equality as economic growth reduced the wealth gap between classes",
            "The expansion of slavery into Northern industrial cities to meet labor demands",
        ],
        "answer": "B",
        "explanation": (
            "The concentration of wage workers in factories and cities created shared conditions "
            "that produced collective labor consciousness. Lowell mill workers organized 'turn-outs' "
            "(strikes) in the 1830s; skilled craftsmen formed early unions; workers formed "
            "political parties advocating for the ten-hour day. Economic growth actually increased "
            "wealth inequality (C is wrong); evangelical religion thrived in industrial cities (A is wrong)."
        ),
    },
    {
        "period": 4,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "\"Brothers! I have listened to many talks from our Great Father [President Jackson]. "
            "When he tells me to go from my home, I feel it hard. But I also know the laws of "
            "the white man are powerful against us. My people have tried to learn his ways—we "
            "have schools, we have a newspaper, we have a written constitution. Yet still he "
            "tells us to go. I must ask: is this the justice of a free people?\""
            " — Attributed to a Cherokee elder, c. 1830 (paraphrased)"
        ),
        "stem": (
            "The Cherokee response to removal, as suggested by this account, most directly "
            "undermines which argument used by supporters of Indian Removal?"
        ),
        "choices": [
            "That Native Americans were militarily incapable of resisting U.S. government policy",
            "That Native peoples were inherently uncivilized and incompatible with American society",
            "That westward expansion was necessary for the growth of American democracy",
            "That the Constitution granted the federal government authority over Native land",
        ],
        "answer": "B",
        "explanation": (
            "Removal supporters like Jackson argued that Native peoples could not assimilate into "
            "American civilization and therefore must be relocated. The Cherokee had directly "
            "contested this by adopting literacy, republican government, Christianity, and market "
            "agriculture. Their sophistication exposed the removal argument as racial ideology "
            "rather than a genuine concern for 'civilization'—the real motivation was land acquisition."
        ),
    },
    {
        "period": 4,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "The Erie Canal, completed in 1825, reduced the cost of shipping goods from Buffalo "
            "to New York City by approximately 95%—from $100 per ton to $5 per ton. Travel time "
            "dropped from three weeks to eight days. Within a decade, New York City had surpassed "
            "Philadelphia and Boston as the nation's largest city and commercial hub. Towns along "
            "the canal route grew rapidly; land values in western New York soared."
        ),
        "stem": (
            "The Erie Canal's impact most directly illustrates which broader pattern in antebellum "
            "American economic development?"
        ),
        "choices": [
            "Federal investment in infrastructure was essential to American economic growth",
            "Transportation improvements accelerated regional economic integration and urbanization",
            "Industrial manufacturing became the dominant sector of the American economy by 1830",
            "Western agricultural expansion reduced economic dependence on Atlantic trade",
        ],
        "answer": "B",
        "explanation": (
            "The Erie Canal dramatically lowered transaction costs, linking Western farms to Eastern "
            "markets and transforming New York into a commercial metropolis. This illustrates how "
            "the 'transportation revolution' integrated previously isolated regional economies into "
            "a national market. The canal was state-funded (New York State), not federally funded, "
            "making A inaccurate. Manufacturing (C) was growing but not yet dominant by 1830."
        ),
    },

    # ── PERIOD 5: 1844–1877 ──────────────────────────────────────────────────
    {
        "period": 5,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"I care not whether slavery is voted down or voted up by the people of a territory, "
            "for that is their right. The great principle at stake is whether the people of a "
            "territory or a new state shall have the right to regulate their own internal concerns "
            "in their own way... If that principle is once established, peace will be restored "
            "between the North and South.\""
            " — Stephen Douglas, Senate debate, 1854 (paraphrased)"
        ),
        "stem": (
            "Douglas's argument for popular sovereignty most directly contributed to which unintended consequence?"
        ),
        "choices": [
            "The collapse of the Second Party System and the emergence of the Republican Party",
            "The strengthening of the Missouri Compromise line as the permanent boundary for slavery",
            "The peaceful resolution of sectional tensions over slavery in the western territories",
            "The legal precedent for Congress to ban slavery in all territories",
        ],
        "answer": "A",
        "explanation": (
            "The Kansas-Nebraska Act's repeal of the Missouri Compromise line outraged Northern "
            "opinion, destroying the Whig Party and fracturing Northern Democrats. Anti-slavery "
            "Whigs, Free Soilers, and Northern Democrats coalesced into the new Republican Party. "
            "Rather than resolving sectional conflict (C), popular sovereignty intensified it, "
            "producing 'Bleeding Kansas' where pro- and anti-slavery settlers fought guerrilla warfare."
        ),
    },
    {
        "period": 5,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "In August 1862, President Lincoln wrote to newspaper editor Horace Greeley: 'My "
            "paramount object in this struggle is to save the Union, and is not either to save "
            "or to destroy slavery. If I could save the Union without freeing any slave I would "
            "do it, and if I could save it by freeing all the slaves I would do that; and if I "
            "could save it by freeing some and leaving others alone I would also do that.' "
            "Six weeks later, Lincoln issued the preliminary Emancipation Proclamation."
        ),
        "stem": (
            "The juxtaposition of Lincoln's letter and the Emancipation Proclamation most directly "
            "suggests which of the following?"
        ),
        "choices": [
            "Lincoln was personally indifferent to slavery and acted purely for strategic reasons",
            "Emancipation was a calculated war measure that Lincoln had already decided upon, framed to maintain broad political support",
            "Lincoln's views on slavery changed dramatically in the six weeks between the letter and the Proclamation",
            "The Emancipation Proclamation was forced on Lincoln by Radical Republicans in Congress",
        ],
        "answer": "B",
        "explanation": (
            "Historians note that Lincoln had already drafted the Proclamation before writing to "
            "Greeley; Secretary of State Seward had advised him to wait for a Union military "
            "victory before announcing it. The letter to Greeley was a public-relations document "
            "designed to retain the support of Unionists who opposed abolition. Lincoln was "
            "managing his coalition while pursuing emancipation—he was not indifferent (A) and "
            "his views had not suddenly changed (C)."
        ),
    },
    {
        "period": 5,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_CCOT,
        "stimulus": (
            "Following the Civil War, Southern state legislatures enacted 'Black Codes' that "
            "required freedpeople to sign annual labor contracts, prohibited them from owning "
            "land in most areas, restricted their freedom of movement, and subjected them to "
            "vagrancy laws under which unemployed Black men could be arrested and hired out as "
            "convict labor. These laws were suspended by Congressional Reconstruction in 1867 "
            "but elements were later revived through convict leasing, Jim Crow segregation, "
            "and sharecropping systems."
        ),
        "stem": (
            "The Black Codes described above most directly illustrate which continuity in "
            "Southern history across the nineteenth and early twentieth centuries?"
        ),
        "choices": [
            "The persistence of plantation agriculture as the foundation of the Southern economy",
            "White Southern efforts to maintain racial control over Black labor through legal mechanisms",
            "The failure of the federal government to intervene in Southern state affairs",
            "The economic dominance of the planter class in post-Civil War Southern politics",
        ],
        "answer": "B",
        "explanation": (
            "The Black Codes reveal that emancipation changed the legal form but not the intent "
            "of racial labor control. When Congressional Reconstruction suspended them, Southern "
            "states invented new legal mechanisms (convict leasing, vagrancy laws, sharecropping "
            "debt peonage, Jim Crow) that served the same function. The continuity is the use of "
            "law to control Black labor and mobility—a pattern that persisted through the mid-twentieth century."
        ),
    },
    {
        "period": 5,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "The Compromise of 1877 ended the disputed Hayes-Tilden presidential election. "
            "Republicans agreed to withdraw the last federal troops from South Carolina and "
            "Louisiana—effectively ending Reconstruction—in exchange for Southern Democrats "
            "accepting Hayes's election. Within months, Redeemer governments in those states "
            "had disenfranchised Black voters and dismantled Reconstruction-era civil rights laws."
        ),
        "stem": (
            "The Compromise of 1877 most directly demonstrated which of the following about "
            "the limits of Reconstruction?"
        ),
        "choices": [
            "The Fourteenth and Fifteenth Amendments were constitutionally insufficient to protect Black rights",
            "The rights of freedpeople were ultimately subordinated to the political interests of the Republican Party",
            "Southern Democrats were willing to accept Black civil rights in exchange for political power",
            "The federal government lacked the constitutional authority to intervene in state elections",
        ],
        "answer": "B",
        "explanation": (
            "The compromise exposed that Republican support for Black civil rights was always "
            "instrumental—tied to political power, not principle. When retaining the presidency "
            "required abandoning Black Southerners, the party made the exchange without hesitation. "
            "This is why historians debate whether Reconstruction 'failed' or was 'betrayed'—the "
            "mechanisms for protecting rights existed; the political will to enforce them did not."
        ),
    },
    {
        "period": 5,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "Historian Eric Foner writes: 'Reconstruction asked too little of the North and "
            "too much of the South. It gave Black men the vote but not the land. Without "
            "economic independence, political rights were fragile... The freedpeople understood "
            "this: 'Give us our own land and we take care of ourselves,' said one freedman, "
            "'but without land, the old masters can hire us or starve us, as they please.' "
            "The failure to redistribute land was the fatal flaw of Reconstruction.'"
        ),
        "stem": (
            "Foner's interpretation most directly challenges which commonly held view of "
            "Reconstruction's failure?"
        ),
        "choices": [
            "That Reconstruction collapsed because freedpeople were politically inexperienced",
            "That Reconstruction failed primarily because of the violent resistance of Southern whites",
            "That Reconstruction failed because Northern Republicans lacked the will to enforce civil rights",
            "That the root cause of Reconstruction's failure was economic rather than purely political",
        ],
        "answer": "D",
        "explanation": (
            "Most traditional explanations of Reconstruction's failure focus on political factors: "
            "Northern fatigue, Democratic resurgence, Southern violence. Foner argues these were "
            "symptoms, not causes. The structural problem was that freedpeople were given legal "
            "rights but remained economically dependent on their former enslavers. Without land "
            "ownership, political rights were meaningless—landlords could use economic coercion "
            "to override the ballot. This is a fundamentally economic argument about the limits "
            "of political Reconstruction without economic transformation."
        ),
    },

    # ── PERIOD 6: 1865–1898 ──────────────────────────────────────────────────
    {
        "period": 6,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"We meet in the midst of a nation brought to the verge of moral, political, and "
            "material ruin. Corruption dominates the ballot-box, the Legislatures, the Congress, "
            "and touches even the ermine of the bench... The newspapers are largely subsidized "
            "or muzzled, public opinion silenced, business prostrated, homes covered with "
            "mortgages, labor impoverished, and the land concentrating in the hands of capitalists.\""
            " — Populist Party Platform, 1892"
        ),
        "stem": (
            "The Populist platform's critique most directly reflected the grievances of which group?"
        ),
        "choices": [
            "Industrial wage workers in Northern cities seeking an eight-hour workday",
            "Southern and Western farmers trapped in debt by falling crop prices and tight credit",
            "Small business owners threatened by the monopolistic practices of railroad corporations",
            "Recent immigrants facing discrimination and political exclusion in Eastern cities",
        ],
        "answer": "B",
        "explanation": (
            "The Populists' core constituency was indebted farmers—especially in the South and "
            "West—who faced falling commodity prices, high railroad freight rates, and limited "
            "access to credit. Their platform demanded railroad regulation, a graduated income tax, "
            "direct election of senators, and inflation of the currency to ease debt burdens. "
            "While workers (A) and small businesses (C) shared some grievances, the party was "
            "rooted in the agrarian crisis of the 1880s–90s."
        ),
    },
    {
        "period": 6,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "Between 1880 and 1920, approximately 20 million immigrants arrived in the United "
            "States, predominantly from Southern and Eastern Europe—Italy, Poland, Russia, "
            "Austria-Hungary, and the Balkans. This 'New Immigration' differed markedly from "
            "earlier waves of Northern and Western European immigrants. The newcomers tended to "
            "cluster in ethnic enclaves in industrial cities, maintain native languages and "
            "traditions, and take industrial rather than agricultural jobs."
        ),
        "stem": (
            "The 'New Immigration' described above most directly contributed to which political development?"
        ),
        "choices": [
            "The passage of the Chinese Exclusion Act and the restriction of Asian immigration",
            "The growth of nativist movements demanding immigration restriction based on national origin",
            "The expansion of settlement houses and social reform efforts in industrial cities",
            "The decline of urban political machines as immigrant communities organized independently",
        ],
        "answer": "B",
        "explanation": (
            "The visible cultural and ethnic difference of Southern and Eastern European immigrants "
            "fueled nativist anxieties about race, religion (most were Catholic or Jewish), and "
            "cultural assimilation. This produced organizations like the Immigration Restriction "
            "League, pseudo-scientific racial theories, and eventually the Emergency Quota Acts "
            "of 1921 and 1924, which used national-origin quotas specifically designed to favor "
            "Northern Europeans over the 'new' immigrants."
        ),
    },
    {
        "period": 6,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "\"In the United States lies half the iron, half the coal, half the silver, and one "
            "third the gold in the world. The country leads in wheat, corn, cotton, and petroleum. "
            "Such conditions, combined with the aggressive spirit and advanced technique of our "
            "people, must inevitably bring the United States into closer contact with foreign "
            "nations... Whether they will or no, Americans must now begin to look outward.\""
            " — Alfred Thayer Mahan, The Influence of Sea Power upon History, 1890 (paraphrased)"
        ),
        "stem": (
            "Mahan's argument most directly provided ideological support for which policy shift "
            "in the 1890s?"
        ),
        "choices": [
            "The adoption of high protective tariffs to defend American industry from foreign competition",
            "American overseas expansion, naval buildup, and acquisition of bases and colonies",
            "The Open Door Policy establishing equal trading rights in China for all nations",
            "The Monroe Doctrine's prohibition of further European colonization in the Americas",
        ],
        "answer": "B",
        "explanation": (
            "Mahan argued that great-power status required a powerful navy, overseas coaling stations, "
            "and control of strategic sea lanes. His ideas directly influenced naval expansion, the "
            "annexation of Hawaii, the acquisition of Guam, the Philippines, and Puerto Rico after "
            "1898, and the construction of the Panama Canal. He provided the strategic rationale "
            "that turned America's industrial strength into an argument for empire."
        ),
    },
    {
        "period": 6,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"The gospel of wealth... insists only that the surplus wealth shall be administered "
            "by its possessors... in the manner which, in their judgment, is best calculated to "
            "produce the most beneficial results for the community—the man of wealth thus becoming "
            "the mere trustee for his poorer brethren... doing for them better than they would or "
            "could do for themselves.\""
            " — Andrew Carnegie, 'The Gospel of Wealth,' 1889"
        ),
        "stem": (
            "Carnegie's 'Gospel of Wealth' most directly reflects which broader ideological "
            "tension of the Gilded Age?"
        ),
        "choices": [
            "The conflict between Protestant and Catholic values in an increasingly diverse society",
            "The tension between celebrating individual wealth accumulation and addressing the social costs of industrialization",
            "The debate between free trade and protectionism in American economic policy",
            "The contradiction between republican self-governance and the growth of corporate power",
        ],
        "answer": "B",
        "explanation": (
            "Carnegie acknowledged the enormous inequality produced by industrial capitalism "
            "but argued it was both natural and beneficial—as long as the wealthy accepted "
            "philanthropic responsibility. This 'Gospel' was a response to socialist criticism "
            "and labor unrest: it conceded that wealth concentration was a social problem while "
            "insisting that charity (not redistribution or regulation) was the solution. The "
            "tension between celebrating industrialists as heroes and confronting poverty "
            "runs through the entire Gilded Age."
        ),
    },
    {
        "period": 6,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_CCOT,
        "stimulus": (
            "In Plessy v. Ferguson (1896), the Supreme Court ruled 7-1 that racially segregated "
            "railroad cars did not violate the Fourteenth Amendment so long as facilities were "
            "'separate but equal.' Justice John Marshall Harlan's lone dissent argued: "
            "'Our Constitution is color-blind, and neither knows nor tolerates classes among "
            "citizens.' The Plessy decision provided constitutional cover for Jim Crow "
            "segregation laws that would govern Southern life for the next sixty years."
        ),
        "stem": (
            "The Plessy decision most directly represented a continuation of which earlier "
            "development in American legal history?"
        ),
        "choices": [
            "The Supreme Court's antebellum ruling in Dred Scott that Black Americans had no constitutional rights",
            "The Slaughterhouse Cases and Civil Rights Cases decisions that had already narrowed Fourteenth Amendment protections",
            "The federal government's policy of allotting Native American land to undermine tribal sovereignty",
            "Congressional Reconstruction legislation that had been invalidated by Democratic-controlled courts",
        ],
        "answer": "B",
        "explanation": (
            "Plessy did not emerge in a vacuum. The Slaughterhouse Cases (1873) had limited the "
            "Fourteenth Amendment's privileges or immunities clause, and the Civil Rights Cases "
            "(1883) had struck down the Civil Rights Act of 1875, ruling that the amendment only "
            "prohibited state—not private—discrimination. Plessy completed this trajectory by "
            "permitting state-mandated segregation, demonstrating a consistent pattern of "
            "judicial erosion of Reconstruction amendments across three decades."
        ),
    },

    # ── PERIOD 7: 1890–1945 ──────────────────────────────────────────────────
    {
        "period": 7,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"I aimed at the public's heart, and by accident I hit it in the stomach.\""
            " — Upton Sinclair, recalling the impact of The Jungle, 1906\n\n"
            "Congress passed the Pure Food and Drug Act and the Meat Inspection Act within "
            "months of the novel's publication. Sinclair had intended his graphic descriptions "
            "of meatpacking conditions to generate sympathy for the exploitation of immigrant "
            "workers; instead, middle-class readers focused on the contamination of their food."
        ),
        "stem": (
            "The gap between Sinclair's intention and the legislation's focus most directly "
            "illustrates which limitation of Progressive Era reform?"
        ),
        "choices": [
            "Progressive reformers lacked the organizational capacity to translate public outrage into legislation",
            "Middle-class reformers were more motivated by consumer protection than by workers' rights or class inequality",
            "The muckraking press was controlled by corporate interests that shaped which reforms gained public attention",
            "Progressive reforms consistently prioritized the interests of recent immigrants over native-born workers",
        ],
        "answer": "B",
        "explanation": (
            "The Jungle episode reveals the class character of Progressive reform. Middle-class "
            "consumers mobilized when they feared eating contaminated meat; they did not mobilize "
            "equivalently for immigrant workers' wages, hours, or safety. The legislation "
            "protected consumers without meaningfully improving labor conditions. This pattern "
            "recurs throughout the Progressive Era: reform was more easily achieved when it "
            "served middle-class interests than when it challenged class hierarchy."
        ),
    },
    {
        "period": 7,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"This is not a peace. It is an armistice for twenty years.\""
            " — Marshal Ferdinand Foch, upon hearing the terms of the Treaty of Versailles, 1919\n\n"
            "The Treaty imposed on Germany: full war guilt (Article 231), reparations of "
            "132 billion gold marks, the loss of 13% of its territory and 10% of its population, "
            "and severe restrictions on its military. American President Woodrow Wilson's Fourteen "
            "Points had promised a peace without 'punitive damages'; the final treaty reflected "
            "primarily French and British demands for security and compensation."
        ),
        "stem": (
            "The Treaty of Versailles most directly contributed to which subsequent development?"
        ),
        "choices": [
            "The U.S. Senate's rejection of League of Nations membership due to sovereignty concerns",
            "The rise of extreme nationalist movements in Germany that exploited resentment of the treaty",
            "Britain and France's adoption of appeasement policies to compensate for the treaty's harshness",
            "The collapse of the Weimar Republic due to the immediate economic burden of reparations",
        ],
        "answer": "B",
        "explanation": (
            "The war guilt clause and reparations gave German nationalists a powerful political "
            "grievance—the 'stab-in-the-back' myth that Germany had been betrayed rather than "
            "defeated. Adolf Hitler's political rise was built on exploiting Versailles resentment. "
            "The Senate's rejection of the League (A) had multiple causes beyond Versailles. "
            "Appeasement (C) was a response to Hitler's rise, not directly to the treaty. "
            "The Weimar Republic survived until 1933 (D is too simplistic)."
        ),
    },
    {
        "period": 7,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"I, too, sing America. / I am the darker brother. / They send me to eat in the "
            "kitchen / When company comes, / But I laugh, / And eat well, / And grow strong. / "
            "Tomorrow, / I'll be at the table / When company comes. / Nobody'll dare / Say to "
            "me, / 'Eat in the kitchen,' / Then. / Besides, / They'll see how beautiful I am / "
            "And be ashamed— / I, too, am America.\""
            " — Langston Hughes, 'I, Too,' 1926"
        ),
        "stem": (
            "Hughes's poem most directly reflects which broader development in African American "
            "culture during the 1920s?"
        ),
        "choices": [
            "The legal strategy of the NAACP to challenge segregation through the courts",
            "The assertion of a distinct Black cultural identity that simultaneously claimed full American belonging",
            "The Great Migration's transformation of African American communities from rural to urban",
            "The pan-African movement's call for Black Americans to connect with African heritage",
        ],
        "answer": "B",
        "explanation": (
            "Hughes's poem captures the dual consciousness at the heart of the Harlem Renaissance: "
            "an assertion of Black cultural pride and beauty combined with an insistence on full "
            "inclusion in American national identity. 'I, Too, am America' directly challenges "
            "the exclusion signified by eating in the kitchen—claiming both pride in Black identity "
            "and equal belonging in the American story. The Great Migration (C) provided the "
            "demographic context but is not what the poem is about."
        ),
    },
    {
        "period": 7,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"Let me assert my firm belief that the only thing we have to fear is fear itself—"
            "nameless, unreasoning, unjustified terror which paralyzes needed efforts to convert "
            "retreat into advance... Our greatest primary task is to put people to work... "
            "I shall ask Congress for the one remaining instrument to meet the crisis—broad "
            "Executive power to wage a war against the emergency, as great as the power that "
            "would be given to me if we were in fact invaded by a foreign foe.\""
            " — Franklin D. Roosevelt, First Inaugural Address, March 4, 1933"
        ),
        "stem": (
            "Roosevelt's use of wartime metaphor in his inaugural address most directly served "
            "which political purpose?"
        ),
        "choices": [
            "Justifying the Supreme Court's broad interpretation of the Commerce Clause",
            "Building public support for the concentration of executive power during the economic crisis",
            "Preparing the American public for possible military conflict with European fascist regimes",
            "Signaling to Congress that he would veto any legislation that limited his economic program",
        ],
        "answer": "B",
        "explanation": (
            "By framing the Depression as a war, FDR invoked a context where Americans "
            "traditionally accept executive leadership, sacrifice, and centralized authority. "
            "The metaphor justified expanding presidential power beyond peacetime norms and "
            "positioned critics of executive action as obstructions to the national defense. "
            "This rhetorical strategy proved effective: in his first hundred days, Congress "
            "delegated enormous authority to the executive branch with little resistance."
        ),
    },
    {
        "period": 7,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_CCOT,
        "stimulus": (
            "Executive Order 9066, signed by President Roosevelt on February 19, 1942, authorized "
            "the removal of approximately 120,000 Japanese Americans—two-thirds of whom were "
            "U.S. citizens—from the West Coast to inland internment camps. The Supreme Court "
            "upheld the order in Korematsu v. United States (1944), ruling that military "
            "necessity justified the racial classification. In 1988, Congress passed the Civil "
            "Liberties Act, formally apologizing and providing reparations to surviving internees."
        ),
        "stem": (
            "The Japanese American internment most directly illustrates which recurring tension "
            "in American history?"
        ),
        "choices": [
            "The conflict between federal and state authority over civil liberties during wartime",
            "The willingness of the government to suspend civil liberties for racial or ethnic minorities during national emergencies",
            "The limits of Supreme Court authority when confronted with executive war powers",
            "The tension between military efficiency and constitutional due process in wartime",
        ],
        "answer": "B",
        "explanation": (
            "The internment illustrates a pattern: during crises, the U.S. government has "
            "repeatedly suspended the rights of racially or ethnically targeted minorities "
            "while leaving similarly situated whites unaffected (German and Italian Americans "
            "were not interned en masse). The racial selectivity of 9066, upheld by Korematsu, "
            "connects to the Palmer Raids, the 1798 Alien Acts, and post-9/11 surveillance—"
            "a continuity of emergency-justified racial targeting."
        ),
    },

    # ── PERIOD 8: 1945–1980 ──────────────────────────────────────────────────
    {
        "period": 8,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"I believe that it must be the policy of the United States to support free peoples "
            "who are resisting attempted subjugation by armed minorities or by outside pressures. "
            "I believe that we must assist free peoples to work out their own destinies in their "
            "own way... The seeds of totalitarian regimes are nurtured by misery and want. They "
            "spread and grow in the evil soil of poverty and strife. They reach their full growth "
            "when the hope of a people for a better life has died.\""
            " — Harry S. Truman, address to Congress, March 12, 1947"
        ),
        "stem": (
            "The Truman Doctrine, as expressed above, most significantly departed from the "
            "precedents established by which earlier foreign policy tradition?"
        ),
        "choices": [
            "The Monroe Doctrine's hemispheric defense perimeter",
            "The Atlantic Charter's commitment to national self-determination",
            "Washington's warning against permanent entangling alliances with European powers",
            "Wilson's Fourteen Points and the principle of collective security through international organizations",
        ],
        "answer": "C",
        "explanation": (
            "The Truman Doctrine's open-ended commitment to 'free peoples' anywhere in the world "
            "directly contradicted the non-entanglement tradition dating to Washington's Farewell "
            "Address. Pre-WWII American foreign policy had repeatedly rejected permanent commitments "
            "to defend other nations. Truman was asking Congress to abandon this tradition permanently "
            "and accept that America's security was inseparable from the global balance of power."
        ),
    },
    {
        "period": 8,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"Have you no sense of decency, sir, at long last? Have you left no sense of decency?\""
            " — Joseph Welch, Army-McCarthy hearings, June 9, 1954\n\n"
            "Senator Joseph McCarthy's Senate Permanent Subcommittee on Investigations had "
            "accused hundreds of government employees, military officers, academics, and "
            "entertainers of communist sympathies. The Army-McCarthy hearings were nationally "
            "televised; polls showed public support for McCarthy collapsed within weeks of Welch's rebuke."
        ),
        "stem": (
            "The Army-McCarthy hearings most directly revealed which factor in the decline "
            "of McCarthyism?"
        ),
        "choices": [
            "The FBI's decision to stop providing McCarthy with investigative support",
            "The Democratic Party's successful mobilization of public opinion against anti-communist overreach",
            "Television's power to expose McCarthy's tactics to a national audience that had previously only read about them",
            "The Supreme Court's ruling that McCarthy's investigative methods violated First Amendment rights",
        ],
        "answer": "C",
        "explanation": (
            "McCarthy had thrived in the medium of press releases and accusations that audiences "
            "only heard about secondhand. Television allowed Americans to watch him directly—"
            "the bullying, the interruptions, the reckless accusations. Welch's rebuke crystallized "
            "the visual impact. The hearings illustrate how the new medium of television could "
            "shape public perception of political figures in ways that earlier media could not."
        ),
    },
    {
        "period": 8,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_ARGUMENT,
        "stimulus": (
            "\"You may well ask: 'Why direct action? Why sit-ins, marches and so forth? Isn't "
            "negotiation a better path?' You are quite right in calling for negotiation. Indeed, "
            "this is the very purpose of direct action. Nonviolent direct action seeks to create "
            "such a crisis and foster such a tension that a community which has constantly refused "
            "to negotiate is forced to confront the issue. It seeks to so dramatize the issue that "
            "it can no longer be ignored.\""
            " — Martin Luther King Jr., Letter from Birmingham Jail, April 16, 1963"
        ),
        "stem": (
            "King's argument in this passage most directly responds to which critique of "
            "the Civil Rights Movement?"
        ),
        "choices": [
            "That civil disobedience was legally equivalent to the laws it protested",
            "That nonviolent protest was ineffective against a violently oppressive system",
            "That direct action was unnecessarily provocative and impeded peaceful negotiation",
            "That the movement's goals were too radical for most white Americans to accept",
        ],
        "answer": "C",
        "explanation": (
            "King is directly addressing white moderates—including Birmingham's white clergy—"
            "who argued that demonstrations were provocative and that Black leaders should "
            "wait for negotiated change. King's counterargument is that direct action is "
            "negotiation by other means: it forces a crisis that compels reluctant parties "
            "to the table. The 'wait' strategy had been used to defer racial justice for "
            "centuries; direct action made inaction politically costly."
        ),
    },
    {
        "period": 8,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "The Gulf of Tonkin Resolution, passed by Congress on August 7, 1964, authorized "
            "the President to 'take all necessary measures to repel any armed attack against "
            "the forces of the United States and to prevent further aggression' in Southeast Asia. "
            "It passed the Senate 88-2. Later investigations revealed that the second alleged "
            "North Vietnamese attack on U.S. destroyers—the incident used to justify the "
            "resolution—almost certainly did not occur."
        ),
        "stem": (
            "The Gulf of Tonkin Resolution most directly represents which broader pattern in "
            "post-WWII American foreign policy?"
        ),
        "choices": [
            "Congress's consistent willingness to delegate war-making authority to the executive branch",
            "The military's ability to fabricate incidents to justify escalating U.S. involvement in foreign conflicts",
            "The Truman Doctrine's requirement that the U.S. respond militarily to communist aggression anywhere",
            "The failure of the CIA to provide accurate intelligence to congressional decision-makers",
        ],
        "answer": "A",
        "explanation": (
            "The Gulf of Tonkin Resolution exemplifies a postwar pattern of Congress ceding "
            "war powers to the executive—enabled by Cold War urgency and bipartisan anti-communism. "
            "Presidents from Truman (Korea) to Johnson (Vietnam) to Bush (Iraq) obtained "
            "broad congressional authorization based on executive-controlled information. "
            "The War Powers Resolution (1973) was a direct response to this pattern, though "
            "it has been of limited effectiveness."
        ),
    },
    {
        "period": 8,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "Lyndon Johnson's Great Society programs (1964–1968) included Medicare and Medicaid, "
            "the Elementary and Secondary Education Act, the Voting Rights Act, the Civil Rights "
            "Act, the Immigration Act of 1965, the creation of the National Endowment for the "
            "Arts and Humanities, and Upward Bound, among dozens of other initiatives. Johnson "
            "declared an 'unconditional war on poverty in America.' Federal spending on social "
            "programs rose from roughly 6% of GDP in 1960 to nearly 10% by 1970."
        ),
        "stem": (
            "The Great Society programs most directly built upon which earlier precedent in "
            "American political history?"
        ),
        "choices": [
            "Theodore Roosevelt's Square Deal and the Progressive Era regulatory state",
            "Franklin Roosevelt's New Deal expansion of the federal government's social welfare role",
            "Harry Truman's Fair Deal proposals for national health insurance and civil rights",
            "Dwight Eisenhower's modern Republicanism and the Interstate Highway Act",
        ],
        "answer": "B",
        "explanation": (
            "The Great Society was a conscious expansion of the New Deal framework: using federal "
            "power to address market failures, reduce poverty, and extend social insurance. "
            "Medicare echoed FDR's Social Security; federal education funding extended New Deal "
            "human capital investment. While Truman's Fair Deal (C) proposed many of the same "
            "programs, it failed to pass; Johnson's success built directly on New Deal institutions "
            "and the political coalition FDR had constructed."
        ),
    },

    # ── PERIOD 9: 1980–Present ────────────────────────────────────────────────
    {
        "period": 9,
        "skill": SKILL_SOURCING,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"Government is not the solution to our problem; government is the problem... "
            "It is time to check and reverse the growth of government, which shows signs of "
            "having grown beyond the consent of the governed... In this present crisis, "
            "government is not the solution to our problem; government is the problem.\""
            " — Ronald Reagan, First Inaugural Address, January 20, 1981"
        ),
        "stem": (
            "Reagan's argument represented a significant departure from which political consensus "
            "that had shaped American policy since the New Deal?"
        ),
        "choices": [
            "The belief that free markets required minimal government interference to function efficiently",
            "The bipartisan acceptance that the federal government had a legitimate role in managing the economy and providing social welfare",
            "The Cold War consensus that military spending was necessary to contain Soviet expansion",
            "The progressive tradition that corporate power required regulation to protect workers and consumers",
        ],
        "answer": "B",
        "explanation": (
            "Since 1933, both parties had accepted the basic New Deal framework—government "
            "responsibility for macroeconomic stability, a social safety net, and regulatory "
            "oversight of markets. Even Eisenhower had preserved and modestly expanded FDR's "
            "programs. Reagan's inauguration challenged this consensus directly, arguing that "
            "the growth of government was itself the problem to be solved, not the mechanism "
            "for solving problems."
        ),
    },
    {
        "period": 9,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CCOT,
        "stimulus": (
            "Between 1979 and 2019, the share of U.S. national income going to the top 1% of "
            "earners rose from approximately 10% to 21%. Over the same period, the federal "
            "marginal tax rate on income above $1 million fell from 70% to 37%. Union membership "
            "in the private sector declined from 24% to 6%. The real (inflation-adjusted) "
            "median household income grew only modestly over four decades, despite substantial "
            "increases in worker productivity."
        ),
        "stem": (
            "The economic trends described above most directly challenge which assumption "
            "underlying the supply-side economic policies of the 1980s?"
        ),
        "choices": [
            "That lower taxes on corporations would encourage investment in domestic manufacturing",
            "That the benefits of economic growth would flow broadly to all income levels",
            "That deregulation of financial markets would reduce the risk of economic crises",
            "That reducing government spending would lower interest rates and stimulate private investment",
        ],
        "answer": "B",
        "explanation": (
            "Supply-side theory ('trickle-down economics') predicted that tax cuts for high "
            "earners would generate growth that raised living standards across income levels. "
            "The data shows the opposite: productivity grew while median wages stagnated, "
            "and the gains from four decades of growth concentrated overwhelmingly at the top. "
            "This is the empirical challenge historians and economists have raised against "
            "the Reagan-era policy framework."
        ),
    },
    {
        "period": 9,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_CAUSATION,
        "stimulus": (
            "\"This will not be another Vietnam. Our troops will have clear and achievable "
            "missions. We will not ask our military to perform a political mission... "
            "I will not commit American troops to a long-term peacekeeping mission in the "
            "midst of a civil war... The specter of Vietnam has been erased.\""
            " — President George H.W. Bush, following the Gulf War victory, 1991"
        ),
        "stem": (
            "Bush's statement most directly reflects which lasting impact of the Vietnam War "
            "on American foreign policy?"
        ),
        "choices": [
            "Congressional resistance to authorizing military force without a formal declaration of war",
            "Public and military reluctance to commit to open-ended land wars with unclear objectives",
            "The military's development of precision-guided weapons to minimize American casualties",
            "The decline of containment as the organizing principle of American foreign policy",
        ],
        "answer": "B",
        "explanation": (
            "The 'Vietnam syndrome'—the public and military resistance to interventions without "
            "clear objectives, exit strategies, and achievable goals—shaped American military "
            "doctrine through the 1980s and 1990s. The Powell Doctrine's insistence on "
            "overwhelming force, clear objectives, and exit strategies was a direct institutional "
            "response to Vietnam. Bush's statement explicitly invoked Vietnam to reassure "
            "Americans that the Gulf War would not repeat those mistakes."
        ),
    },
    {
        "period": 9,
        "skill": SKILL_CONNECT,
        "reasoning": HRP_CONTEXT,
        "stimulus": (
            "\"There is not a liberal America and a conservative America—there is the United "
            "States of America. There is not a Black America and a White America and Latino "
            "America and Asian America—there's the United States of America... Do we participate "
            "in a politics of cynicism or do we participate in a politics of hope?\""
            " — Barack Obama, keynote address, Democratic National Convention, July 27, 2004"
        ),
        "stem": (
            "Obama's 2004 speech was delivered in the context of which broader political development?"
        ),
        "choices": [
            "A period of bipartisan cooperation in Congress following the September 11 attacks",
            "Intensifying political polarization along partisan, ideological, and demographic lines",
            "Growing public support for third-party candidates as alternatives to partisan gridlock",
            "A resurgence of liberal political philosophy following the failures of the Reagan Revolution",
        ],
        "answer": "B",
        "explanation": (
            "Obama's appeal to a unified American identity was a rhetorical response to—and "
            "evidence of—the deep polarization that had developed through the culture wars of "
            "the 1990s, the contested 2000 election, and the Iraq War debate. His speech "
            "resonated precisely because it rejected the binary 'red state/blue state' framing "
            "that defined the era. The context makes it a document of its polarized moment, "
            "not evidence that polarization had ended."
        ),
    },
    {
        "period": 9,
        "skill": SKILL_CLAIMS,
        "reasoning": HRP_COMPARISON,
        "stimulus": (
            "The USA PATRIOT Act (2001) expanded government surveillance authority, allowed "
            "'sneak and peek' searches without immediate notification, permitted 'roving wiretaps,' "
            "and authorized collection of business records including library and bookstore "
            "transactions. It passed the Senate 98-1. Edward Snowden's 2013 leaks revealed "
            "that the NSA had used legal authorities to conduct bulk collection of phone metadata "
            "on millions of Americans. Civil liberties organizations argued these practices "
            "violated the Fourth Amendment."
        ),
        "stem": (
            "The civil liberties debate surrounding the PATRIOT Act most directly parallels "
            "which earlier episode in American history?"
        ),
        "choices": [
            "The Alien and Sedition Acts of 1798, which criminalized criticism of the government during the Quasi-War",
            "The internment of Japanese Americans during World War II, justified by claims of military necessity",
            "McCarthyism and the Second Red Scare, which used national security fears to justify broad surveillance of political dissidents",
            "The Espionage and Sedition Acts of 1917–18, which criminalized anti-war speech during World War I",
        ],
        "answer": "C",
        "explanation": (
            "The PATRIOT Act surveillance programs most directly parallel the McCarthy era: both "
            "involved broad government monitoring of citizens' associations and communications "
            "justified by national security; both generated significant civil liberties criticism; "
            "both were enabled by bipartisan fear of an ideological enemy. The Japanese internment "
            "(B) is a closer parallel in some respects but involved physical deprivation of liberty, "
            "while the PATRIOT Act/McCarthy parallel centers on surveillance and political monitoring."
        ),
    },
]

# Fix the reasoning label used in Period 8 Question 3 (used HRP_ARGUMENT accidentally)
HRP_ARGUMENT = SKILL_ARGUMENT  # alias so the data above doesn't error


# ─── Claude batch generation ──────────────────────────────────────────────────

# AP exam skill and reasoning combinations to vary across generated questions
AP_SKILLS = [
    ("Sourcing & Situation", "evaluating the author's point of view, purpose, historical situation, or audience"),
    ("Claims & Evidence", "analyzing a specific claim or piece of evidence within a stimulus"),
    ("Contextualization", "connecting the stimulus to broader historical context"),
    ("Making Connections", "comparing, connecting, or tracing causation/change across time or place"),
    ("Argumentation", "evaluating a historical argument or interpretation"),
]

AP_REASONING = [
    ("Causation", "identifying causes or effects of historical developments"),
    ("Comparison", "comparing historical developments, societies, or arguments"),
    ("Continuity & Change Over Time", "tracing what changed and what persisted across a time period"),
]

STIMULUS_FORMATS = [
    "a primary source document (speech excerpt, letter, political pamphlet, congressional testimony, or diary entry)",
    "an excerpt from a secondary source (a historian's published argument about a historical development)",
    "a description of a political cartoon, engraving, or photograph with key visual details explained",
    "a statistical table or data showing population, economic, or demographic trends",
    "an excerpt from a newspaper editorial, magazine article, or public address",
]


def generate_claude_batch(period_num: int, n: int = 3) -> list[dict]:
    """Ask Claude to generate n harder stimulus-based APUSH MCQs for the given period."""
    period_range, period_name = PERIODS[period_num]

    # Pick varied skill/reasoning combos
    skills = random.sample(AP_SKILLS, min(n, len(AP_SKILLS)))
    reasonings = random.sample(AP_REASONING, min(n, len(AP_REASONING)))
    formats = random.sample(STIMULUS_FORMATS, min(n, len(STIMULUS_FORMATS)))

    question_specs = []
    for i in range(n):
        skill_name, skill_desc = skills[i % len(skills)]
        reasoning_name, reasoning_desc = reasonings[i % len(reasonings)]
        fmt = formats[i % len(formats)]
        question_specs.append(
            f"Question {i+1}: Skill = {skill_name} ({skill_desc}) | "
            f"Reasoning = {reasoning_name} ({reasoning_desc}) | "
            f"Stimulus format = {fmt}"
        )

    specs_text = "\n".join(question_specs)

    prompt = f"""You are an AP United States History exam question writer for the College Board.

Generate exactly {n} challenging, stimulus-based multiple choice questions for APUSH Period {period_num} ({period_range}: {period_name}).

SPECIFICATIONS FOR EACH QUESTION:
{specs_text}

REQUIREMENTS (apply to ALL questions):
1. Each question MUST have a realistic, historically accurate stimulus (3–6 sentences). You may write plausible primary source excerpts in period-appropriate voice, or invent realistic statistical data grounded in actual historical trends.
2. Questions must test ANALYSIS, not recall. Students who only memorized facts should find at least two choices plausible. The correct answer requires reading the stimulus critically combined with historical context.
3. All four answer choices (A–D) must be historically plausible. Wrong answers should reflect common student misconceptions or superficial readings of the stimulus.
4. Avoid questions that are answered purely by reading the stimulus without historical knowledge, and avoid questions that can be answered without reading the stimulus.
5. The explanation must identify WHY wrong answers fail—not just why the right answer is correct.
6. Cover different topics/themes within the period across the {n} questions—do not repeat the same event or theme.

Use this EXACT format for each question, with no extra text between questions:

--- QUESTION 1 ---
SKILL: [skill name from specification]
REASONING: [reasoning process from specification]
STIMULUS:
[stimulus text]
QUESTION:
[question stem]
A) [choice]
B) [choice]
C) [choice]
D) [choice]
ANSWER: [A/B/C/D]
EXPLANATION:
[explanation — must address why wrong answers fail]

--- QUESTION 2 ---
[same format]

--- QUESTION 3 ---
[same format]"""

    try:
        print(dim(f"  Generating {n} Claude questions for Period {period_num}..."), end="", flush=True)
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=3500,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            raw = stream.get_final_message()
        print(dim(" done."))

        text = next(b.text for b in raw.content if b.type == "text")
        return _parse_claude_batch(text, period_num)
    except Exception as e:
        print(red(f"\n  [Claude generation failed: {e}]"))
        return []


def _parse_claude_batch(text: str, period_num: int) -> list[dict]:
    """Parse Claude's batch response into a list of question dicts."""
    questions = []
    # Split on question delimiters
    import re
    blocks = re.split(r"---\s*QUESTION\s+\d+\s*---", text)
    for block in blocks:
        if not block.strip():
            continue
        q = _parse_single_block(block.strip(), period_num)
        if q:
            questions.append(q)
    return questions


def _parse_single_block(block: str, period_num: int) -> dict | None:
    """Parse one question block from Claude's response."""
    try:
        lines = block.splitlines()
        skill, reasoning, stimulus, question_stem = "", "", "", ""
        choices: list[str] = []
        answer, explanation = "", ""
        section = None
        buf: list[str] = []

        for line in lines:
            s = line.strip()
            if s.startswith("SKILL:"):
                skill = s.replace("SKILL:", "").strip()
            elif s.startswith("REASONING:"):
                reasoning = s.replace("REASONING:", "").strip()
            elif s == "STIMULUS:":
                section = "stimulus"; buf = []
            elif s == "QUESTION:":
                if section == "stimulus":
                    stimulus = " ".join(buf).strip()
                section = "question"; buf = []
            elif len(s) >= 2 and s[0] in "ABCD" and s[1] == ")":
                if section == "question":
                    question_stem = " ".join(buf).strip()
                section = "choices"
                choices.append(s[2:].strip())
            elif s.startswith("ANSWER:"):
                raw_ans = s.replace("ANSWER:", "").strip().upper()
                answer = raw_ans[0] if raw_ans else ""
            elif s == "EXPLANATION:":
                section = "explanation"; buf = []
            else:
                if section in ("stimulus", "question", "explanation"):
                    buf.append(s)

        if section == "explanation":
            explanation = " ".join(buf).strip()

        if not question_stem or len(choices) != 4 or answer not in "ABCD" or not explanation:
            return None

        return {
            "period": period_num,
            "skill": skill or SKILL_CLAIMS,
            "reasoning": reasoning or HRP_CAUSATION,
            "stimulus": stimulus,
            "stem": question_stem,
            "choices": choices,
            "answer": answer,
            "explanation": explanation,
            "claude_generated": True,
        }
    except Exception:
        return None


# ─── Display helpers ───────────────────────────────────────────────────────────
WRAP = 82

def wrap(text: str, indent: int = 0) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=WRAP, initial_indent=prefix, subsequent_indent=prefix)


def display_question(q: dict, number: int, total: int):
    print()
    print(cyan("─" * WRAP))

    # Header line
    header = f"  {bold(f'Question {number}/{total}')}  |  Period {q['period']}: {PERIODS[q['period']][0]}"
    print(header)

    # Skill / Reasoning tags
    skill = q.get("skill", "")
    reasoning = q.get("reasoning", "")
    meta = ""
    if skill:
        meta += f"  {blue(f'[{skill}]')}"
    if reasoning:
        meta += f"  {blue(f'[{reasoning}]')}"
    if q.get("claude_generated"):
        meta += f"  {yellow('★ Claude Generated Question')}"
    if meta:
        print(meta)

    print(cyan("─" * WRAP))

    # Stimulus
    if q.get("stimulus"):
        print()
        print(bold("  STIMULUS"))
        print(dim("  " + "─" * 40))
        for para in q["stimulus"].split("\n"):
            para = para.strip()
            if para:
                for line in textwrap.wrap(para, width=WRAP - 4):
                    print(f"    {dim(line)}")
        print()

    # Question stem
    print(wrap(q["stem"], indent=2))
    print()

    # Choices
    labels = ["A", "B", "C", "D"]
    for label, choice in zip(labels, q["choices"]):
        print(wrap(f"  {bold(label)})  {choice}", indent=6))
    print()


def get_answer() -> str:
    while True:
        raw = input(bold("  Your answer (A/B/C/D) or Q to quit: ")).strip().upper()
        if raw in ("A", "B", "C", "D", "Q"):
            return raw
        print(red("  Please enter A, B, C, or D."))


def show_feedback(q: dict, user_ans: str):
    correct = q["answer"]
    print()
    if user_ans == correct:
        print(green(f"  ✓  Correct!  The answer is {bold(correct)}."))
    else:
        print(red(f"  ✗  Incorrect.  You chose {bold(user_ans)}; the correct answer is {bold(correct)}."))
    print()
    print(bold("  Explanation:"))
    print(wrap(q["explanation"], indent=4))


# ─── Quiz logic ────────────────────────────────────────────────────────────────
def build_question_pool(
    selected_periods: list[int],
    n_prewritten: int,
    n_claude_per_period: int,
) -> list[dict]:
    pool: list[dict] = []

    # Pre-written
    candidates = [q for q in PREWRITTEN if q["period"] in selected_periods]
    random.shuffle(candidates)
    pool.extend(candidates[:n_prewritten])

    # Claude batch generation
    if n_claude_per_period > 0:
        periods_to_gen = random.sample(selected_periods, len(selected_periods))
        total_needed = n_claude_per_period * len(selected_periods)
        generated = 0
        for p in periods_to_gen:
            if generated >= total_needed:
                break
            batch_size = min(3, n_claude_per_period)
            batch = generate_claude_batch(p, n=batch_size)
            pool.extend(batch)
            generated += len(batch)

    random.shuffle(pool)
    return pool


def run_quiz(questions: list[dict]):
    total = len(questions)
    score = 0
    wrong: list[dict] = []
    answered = 0

    for i, q in enumerate(questions, 1):
        display_question(q, i, total)
        ans = get_answer()
        if ans == "Q":
            print(yellow("\n  Quiz ended early."))
            break
        answered += 1
        show_feedback(q, ans)
        if ans == q["answer"]:
            score += 1
        else:
            wrong.append({**q, "user_answer": ans})
        input(dim("  [Press Enter for next question]"))

    if answered == 0:
        return

    print()
    print(cyan("═" * WRAP))
    pct = score / answered * 100
    print(bold(f"  FINAL SCORE:  {score} / {answered}  ({pct:.0f}%)"))

    # AP 5-scale mapping (rough)
    if pct >= 75:
        grade = green("Likely 4–5  ✓  Strong performance!")
    elif pct >= 60:
        grade = yellow("Likely 3–4  —  Keep studying!")
    elif pct >= 45:
        grade = yellow("Likely 2–3  —  More review needed.")
    else:
        grade = red("Likely 1–2  —  Significant review needed.")
    print(f"  {grade}")
    print(cyan("═" * WRAP))

    # Skill breakdown
    if answered >= 3:
        from collections import defaultdict
        skill_scores: dict = defaultdict(lambda: [0, 0])
        for q in questions[:answered]:
            sk = q.get("skill", "Unknown")
            skill_scores[sk][1] += 1
            if q.get("user_answer", q["answer"]) == q["answer"]:
                skill_scores[sk][0] += 1
        # Mark wrong ones
        wrong_ids = {id(q) for q in wrong}
        skill_scores2: dict = defaultdict(lambda: [0, 0])
        answered_qs = questions[:answered]
        wrong_stems = {q["stem"] for q in wrong}
        for q in answered_qs:
            sk = q.get("skill", "Unknown")
            skill_scores2[sk][1] += 1
            if q["stem"] not in wrong_stems:
                skill_scores2[sk][0] += 1

        print()
        print(bold("  Skill Breakdown:"))
        for sk, (got, tot) in sorted(skill_scores2.items()):
            pct_sk = got / tot * 100 if tot else 0
            bar = "█" * int(pct_sk / 10) + "░" * (10 - int(pct_sk / 10))
            color = green if pct_sk >= 70 else (yellow if pct_sk >= 50 else red)
            print(f"    {sk:<32} {color(bar)}  {got}/{tot}")

    # Missed question review
    if wrong:
        print()
        review = input(bold("  Review missed questions? (y/n): ")).strip().lower()
        if review == "y":
            print()
            print(bold("  ─── MISSED QUESTIONS REVIEW ───"))
            for q in wrong:
                print()
                print(cyan("─" * WRAP))
                meta = f"  Period {q['period']}: {PERIODS[q['period']][0]}"
                if q.get("skill"):
                    meta += f"  {blue(f'[{q[\"skill\"]}]')}"
                if q.get("reasoning"):
                    meta += f"  {blue(f'[{q[\"reasoning\"]}]')}"
                if q.get("claude_generated"):
                    meta += f"  {yellow('★ Claude Generated Question')}"
                print(meta)

                if q.get("stimulus"):
                    print(bold("\n  STIMULUS"))
                    print(dim("  " + "─" * 40))
                    for line in textwrap.wrap(q["stimulus"], width=WRAP - 4):
                        print(f"    {dim(line)}")

                print()
                print(wrap(q["stem"], indent=2))
                print()
                labels = ["A", "B", "C", "D"]
                for label, choice in zip(labels, q["choices"]):
                    if label == q["answer"]:
                        marker = green(f"  ← correct ({label})")
                        print(wrap(f"  {bold(label)})  {choice}{marker}", indent=6))
                    elif label == q["user_answer"]:
                        marker = red(f"  ← your answer ({label})")
                        print(wrap(f"  {bold(label)})  {choice}{marker}", indent=6))
                    else:
                        print(wrap(f"  {bold(label)})  {choice}", indent=6))
                print()
                print(bold("  Explanation:"))
                print(wrap(q["explanation"], indent=4))
            print()


# ─── Main menu ─────────────────────────────────────────────────────────────────
def print_banner():
    print()
    print(cyan("╔" + "═" * 68 + "╗"))
    print(cyan("║") + bold("       AP United States History  ·  MCQ Practice Tool           ") + cyan(" ║"))
    print(cyan("╠" + "═" * 68 + "╣"))
    print(cyan("║") + f"  {dim('All questions are stimulus-based, matching the redesigned AP exam')}   " + cyan("║"))
    print(cyan("║") + f"  {blue('[Skill]')} {blue('[Reasoning]')} labels on every question                       " + cyan("║"))
    print(cyan("║") + f"  {yellow('★ Claude Generated')} = AI-crafted, harder than typical online MCQs     " + cyan("║"))
    print(cyan("╚" + "═" * 68 + "╝"))
    print()


def select_periods() -> list[int]:
    print(bold("  ── Select Period(s) ──"))
    print()
    for num, (rng, name) in PERIODS.items():
        count = sum(1 for q in PREWRITTEN if q["period"] == num)
        print(f"    {bold(str(num))})  Period {num}  {rng}  —  {name}  {dim(f'({count} pre-written)')}")
    print()
    print(f"    {bold('A')})  All periods (mixed)")
    print()

    while True:
        raw = input(bold("  Enter period number(s) separated by commas, or A for all: ")).strip().upper()
        if raw == "A":
            return list(PERIODS.keys())
        try:
            chosen = [int(x.strip()) for x in raw.split(",")]
            if all(1 <= c <= 9 for c in chosen):
                return list(set(chosen))
            print(red("  Please enter numbers between 1 and 9."))
        except ValueError:
            print(red("  Invalid input. Try again."))


def select_count(label: str, default: int, max_val: int) -> int:
    while True:
        raw = input(bold(f"  {label} [default {default}, max {max_val}]: ")).strip()
        if raw == "":
            return default
        try:
            n = int(raw)
            if 0 <= n <= max_val:
                return n
            print(red(f"  Enter 0–{max_val}."))
        except ValueError:
            print(red("  Please enter a number."))


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(red("\n  Error: ANTHROPIC_API_KEY environment variable is not set."))
        print(red("  Set it with:  export ANTHROPIC_API_KEY='your-key-here'\n"))
        sys.exit(1)

    print_banner()

    while True:
        periods = select_periods()
        print()

        avail = len([q for q in PREWRITTEN if q["period"] in periods])
        print(dim(f"  {avail} pre-written questions available for selected period(s)."))
        print(dim(f"  Claude questions are generated in batches of 3 (one API call per period selected)."))
        print()

        n_pre = select_count(
            "# of pre-written questions",
            default=min(5, avail),
            max_val=avail,
        )
        n_claude_per_period = select_count(
            "# of Claude-generated questions per period (3 per API call)",
            default=1 if len(periods) <= 3 else 0,
            max_val=6,
        )
        print()

        if n_pre == 0 and n_claude_per_period == 0:
            print(red("  Select at least one question source. Try again."))
            continue

        if n_claude_per_period > 0:
            estimated_calls = len(periods)
            print(dim(f"  This will make {estimated_calls} API call(s) to generate questions..."))
            print()

        questions = build_question_pool(periods, n_pre, n_claude_per_period)

        if not questions:
            print(red("  No questions could be loaded. Please try again."))
            continue

        print(dim(f"  Quiz ready: {len(questions)} questions total."))
        input(bold("  Press Enter to begin..."))

        run_quiz(questions)

        print()
        again = input(bold("  Start a new quiz? (y/n): ")).strip().lower()
        if again != "y":
            print(cyan("\n  Good luck on your exam!\n"))
            break


if __name__ == "__main__":
    main()
