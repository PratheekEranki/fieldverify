"""Common English given-name equivalents. Each tuple is one group of interchangeable names."""
NICKNAME_GROUPS: list[tuple[str, ...]] = [
    ("robert", "bob", "bobby", "rob", "robbie", "bert"),
    ("william", "bill", "billy", "will", "willie", "liam"),
    ("richard", "rick", "ricky", "dick", "rich"),
    ("james", "jim", "jimmy", "jamie"),
    ("john", "jack", "johnny", "jon"),
    ("joseph", "joe", "joey"),
    ("michael", "mike", "mikey", "mick"),
    ("thomas", "tom", "tommy"),
    ("charles", "charlie", "chuck", "chas"),
    ("christopher", "chris", "kit"),
    ("daniel", "dan", "danny"),
    ("matthew", "matt", "matty"),
    ("anthony", "tony"),
    ("edward", "ed", "eddie", "ted", "ned"),
    ("steven", "stephen", "steve"),
    ("andrew", "andy", "drew"),
    ("benjamin", "ben", "benny"),
    ("samuel", "sam", "sammy"),
    ("alexander", "alex", "al", "xander"),
    ("nicholas", "nick", "nicky"),
    ("jonathan", "jon", "jonny"),
    ("gregory", "greg"),
    ("timothy", "tim", "timmy"),
    ("kenneth", "ken", "kenny"),
    ("patrick", "pat", "paddy"),
    ("elizabeth", "liz", "lizzie", "beth", "betty", "eliza", "betsy"),
    ("margaret", "maggie", "meg", "peggy", "marge"),
    ("katherine", "catherine", "kathryn", "kate", "katie", "kathy", "cathy", "kat"),
    ("jennifer", "jen", "jenny"),
    ("rebecca", "becky", "becca"),
    ("susan", "sue", "suzy"),
    ("patricia", "pat", "patty", "trish", "tricia"),
    ("deborah", "debra", "deb", "debbie"),
    ("victoria", "vicky", "tori"),
    ("christine", "christina", "chris", "tina"),
    ("jessica", "jess", "jessie"),
    ("abigail", "abby"),
    ("samantha", "sam", "sammy"),
    ("alexandra", "alex", "alexa", "sandra", "sandy"),
    ("josephine", "jo", "josie"),
    ("barbara", "barb", "barbie"),
    ("dorothy", "dot", "dottie"),
]

_EQUIV: dict[str, set[str]] = {}
for group in NICKNAME_GROUPS:
    for name in group:
        _EQUIV.setdefault(name, set()).update(group)


def are_nickname_equivalent(a: str, b: str) -> bool:
    """True if two normalized first names belong to the same nickname group (e.g. bob ~ robert)."""
    return a != b and b in _EQUIV.get(a, set())
