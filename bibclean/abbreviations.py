"""Deterministic venue aliases and the user's exact abbreviation spellings.

Repeated keys use the last supplied value (TOG = ACM TOG). No fuzzy matching.
Keep these spellings even where another style guide would abbreviate differently.
"""

from __future__ import annotations

import re

from .bibliography import normalized

# key, user-supplied abbreviation, recognized full names / prior short forms
VENUES = [
    (
        "TPAMI",
        "IEEE Trans. Pattern Anal. Mach. Intell.",
        ["IEEE Transactions on Pattern Analysis and Machine Intelligence"],
    ),
    ("IJCV", "Int. J. Comput. Vis.", ["International Journal of Computer Vision"]),
    ("TOG", "ACM TOG", ["ACM Transactions on Graphics", "ACM Trans. Graph."]),
    ("TIP", "IEEE Trans. Image Process.", ["IEEE Transactions on Image Processing"]),
    (
        "TVCG",
        "IEEE Trans. Vis. Comput. Graph.",
        ["IEEE Transactions on Visualization and Computer Graphics"],
    ),
    ("TMM", "IEEE Trans. Multimedia", ["IEEE Transactions on Multimedia"]),
    ("ACCV", "ACCV", ["Asian Conference on Computer Vision", "Computer Vision ACCV"]),
    (
        "AAAI",
        "AAAI",
        [
            "AAAI Conference on Artificial Intelligence",
            "Association for the Advancement of Artificial Intelligence Conference on Artificial Intelligence",
        ],
    ),
    (
        "CVPRW",
        "CVPRW",
        [
            "IEEE Conference on Computer Vision and Pattern Recognition Workshops",
            "IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops",
            "IEEE Computer Society Conference on Computer Vision and Pattern Recognition Workshops",
            "Conference on Computer Vision and Pattern Recognition Workshops",
            "CVPR Workshops",
        ],
    ),
    (
        "TCSVT",
        "IEEE Trans. Circuit Syst. Video Technol.",
        [
            "IEEE Transactions on Circuits and Systems for Video Technology",
            "IEEE Trans. Circuits Syst. Video Technol.",
        ],
    ),
    (
        "SPL",
        "IEEE Sign. Process. Letters",
        ["IEEE Signal Processing Letters", "IEEE Signal Process. Lett."],
    ),
    ("VR", "Vis. Res.", ["Vision Research"]),
    ("JOV", "J. Vis.", ["Journal of Vision"]),
    ("TVC", "The Vis. Comput.", []),
    ("JCST", "J. Comput. Sci. Tech.", ["Journal of Computer Science and Technology"]),
    ("CGF", "Comput. Graph. Forum", ["Computer Graphics Forum"]),
    ("CVM", "Computational Visual Media", []),
    ("SPM", "IEEE Signal Process. Mag.", ["IEEE Signal Processing Magazine"]),
    (
        "CVPR",
        "CVPR",
        [
            "IEEE Conference on Computer Vision and Pattern Recognition",
            "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
            "IEEE Computer Society Conference on Computer Vision and Pattern Recognition",
            "Conference on Computer Vision and Pattern Recognition",
            "Computer Vision and Pattern Recognition",
        ],
    ),
    (
        "ICCV",
        "ICCV",
        [
            "IEEE International Conference on Computer Vision",
            "IEEE/CVF International Conference on Computer Vision",
            "International Conference on Computer Vision",
        ],
    ),
    ("ECCV", "ECCV", ["European Conference on Computer Vision", "Computer Vision ECCV"]),
    (
        "NIPS",
        "NeurIPS",
        [
            "NeurIPS",
            "Advances in Neural Information Processing Systems",
            "Conference on Neural Information Processing Systems",
            "Neural Information Processing Systems",
        ],
    ),
    (
        "ICPR",
        "ICPR",
        [
            "International Conference on Pattern Recognition",
            "IEEE International Conference on Pattern Recognition",
        ],
    ),
    ("BMVC", "BMVC", ["British Machine Vision Conference"]),
    (
        "ACMMM",
        "ACM MM",
        [
            "ACM International Conference on Multimedia",
            "ACM Multimedia",
            "ACM International Conference on Multi-media",
            "ACM MM",
        ],
    ),
    (
        "ICME",
        "ICME",
        [
            "IEEE International Conference on Multimedia and Expo",
            "IEEE International Conference on Multimedia & Expo",
            "International Conference on Multimedia and Expo",
        ],
    ),
    (
        "ICASSP",
        "ICASSP",
        [
            "IEEE International Conference on Acoustics, Speech and Signal Processing",
            "IEEE International Conference on Acoustics, Speech, and Signal Processing",
            "International Conference on Acoustics, Speech and Signal Processing",
        ],
    ),
    (
        "ICIP",
        "ICIP",
        [
            "IEEE International Conference on Image Processing",
            "International Conference on Image Processing",
        ],
    ),
    ("ICLR", "ICLR", ["International Conference on Learning Representations"]),
    (
        "IROS",
        "IROS",
        [
            "IEEE/RSJ International Conference on Intelligent Robots and Systems",
            "International Conference on Intelligent Robots and Systems",
        ],
    ),
    (
        "ICRA",
        "ICRA",
        [
            "IEEE International Conference on Robotics and Automation",
            "International Conference on Robotics and Automation",
        ],
    ),
    ("IJCAI", "IJCAI", ["International Joint Conference on Artificial Intelligence"]),
    ("PR", "Pattern Recognit.", ["Pattern Recognition"]),
    ("ACCESS", "IEEE Access", []),
    ("RAL", "IEEE RA-L", ["IEEE Robotics and Automation Letters", "IEEE Robot. Autom. Lett."]),
    ("SENSJ", "IEEE Sensors J.", ["IEEE Sensors Journal"]),
    ("TII", "IEEE Trans. Ind. Informat.", ["IEEE Transactions on Industrial Informatics"]),
    ("TIM", "IEEE Trans. Instrum. Meas.", ["IEEE Transactions on Instrumentation and Measurement"]),
    ("TVT", "IEEE Trans. Veh. Technol.", ["IEEE Transactions on Vehicular Technology"]),
    ("IF", "Inf. Fusion", ["Information Fusion"]),
    ("JMS", "J. Manuf. Syst.", ["Journal of Manufacturing Systems"]),
    ("MEAS", "Measurement", []),
    ("SIGPRO", "Signal Process.", ["Signal Processing"]),
    ("PRL", "Pattern Recognit. Lett.", ["Pattern Recognition Letters"]),
    ("APOPT", "Appl. Opt.", ["Applied Optics"]),
    ("OE", "Opt. Eng.", ["Optical Engineering"]),
    ("TVCOMP", "Vis. Comput.", ["The Visual Computer", "Visual Computer"]),
    ("SENSORS", "Sensors", []),
    ("REMOTES", "Remote Sens.", ["Remote Sensing"]),
    ("DISPLAYS", "Displays", []),
    ("ELECTRON", "Electronics", []),
    ("APPSCI", "Appl. Sci.", ["Applied Sciences"]),
    (
        "WACV",
        "WACV",
        [
            "IEEE Winter Conference on Applications of Computer Vision",
            "IEEE/CVF Winter Conference on Applications of Computer Vision",
            "Winter Conference on Applications of Computer Vision",
            "IEEE Workshop on Applications of Computer Vision",
        ],
    ),
    (
        "EDGE",
        "ACM/IEEE Symp. Edge Comput.",
        [
            "ACM/IEEE Symposium on Edge Computing",
            "IEEE/ACM Symposium on Edge Computing",
            "Symposium on Edge Computing",
        ],
    ),
    (
        "ICCVW",
        "ICCVW",
        [
            "IEEE International Conference on Computer Vision Workshops",
            "IEEE/CVF International Conference on Computer Vision Workshops",
            "International Conference on Computer Vision Workshops",
            "ICCV Workshops",
        ],
    ),
    (
        "TITS",
        "IEEE Trans. Intell. Transp. Syst.",
        ["IEEE Transactions on Intelligent Transportation Systems"],
    ),
    ("TIV", "IEEE Trans. Intell. Veh.", ["IEEE Transactions on Intelligent Vehicles"]),
    ("JIMG", "J. Imaging", ["Journal of Imaging"]),
    ("JCHEMED", "J. Chem. Educ.", ["Journal of Chemical Education"]),
    ("MTA", "Multimedia Tools Appl.", ["Multimedia Tools and Applications"]),
    ("OPTCOMM", "Opt. Commun.", ["Optics Communications"]),
    ("OER", "Opto-Electron. Rev.", ["Opto-Electronics Review"]),
    ("PEERJCS", "PeerJ Comput. Sci.", ["PeerJ Computer Science"]),
    (
        "PIMECHD",
        "Proc. Inst. Mech. Eng., Part D: J. Automob. Eng.",
        [
            "Proceedings of the Institution of Mechanical Engineers, Part D: Journal of Automobile Engineering"
        ],
    ),
    ("SCIDATA", "Sci. Data", ["Scientific Data"]),
    ("NATCOMM", "Nat. Commun.", ["Nature Communications"]),
    (
        "IJRR",
        "Int. J. Robot. Res.",
        [
            "The International Journal of Robotics Research",
            "International Journal of Robotics Research",
        ],
    ),
    (
        "ISPRS",
        "ISPRS J. Photogramm. Remote Sens.",
        ["ISPRS Journal of Photogrammetry and Remote Sensing"],
    ),
    ("VTM", "IEEE Veh. Technol. Mag.", ["IEEE Vehicular Technology Magazine"]),
    ("IJAT", "Int. J. Automot. Technol.", ["International Journal of Automotive Technology"]),
    ("ARS", "Adv. Radio Sci.", ["Advances in Radio Science"]),
    ("JCD", "J. Control Decis.", ["Journal of Control and Decision"]),
]

CONFERENCES = {
    "ACCV",
    "AAAI",
    "CVPRW",
    "CVPR",
    "ICCV",
    "ECCV",
    "NIPS",
    "ICPR",
    "BMVC",
    "ACMMM",
    "ICME",
    "ICASSP",
    "ICIP",
    "ICLR",
    "IROS",
    "ICRA",
    "IJCAI",
    "WACV",
    "EDGE",
    "ICCVW",
}
BY_KEY = {key.casefold(): (key, short) for key, short, _ in VENUES}
ALIASES = {
    normalized(alias): (key, short)
    for key, short, aliases in VENUES
    for alias in [key, short, *aliases]
}
CONFERENCE_ALIASES = {
    alias: record for alias, record in ALIASES.items() if record[0] in CONFERENCES
}


def abbreviation(value, expression=""):
    """Return an exact dictionary match, never a similarity-based guess."""
    bare = expression.strip()
    if re.fullmatch(r"[A-Za-z][\w-]*", bare) and bare.casefold() in BY_KEY:
        return BY_KEY[bare.casefold()]
    name = normalized(value)
    if name in ALIASES:
        return ALIASES[name]
    # Conference metadata commonly adds a year, edition, or trailing acronym.
    # Only these decorations are removed; workshop and joint-event words stay.
    name = re.sub(r"\b(?:19|20)\d{2}\b|\b\d+(?:st|nd|rd|th)\b", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"^(?:proceedings(?: of)?(?: the)?|proc(?: of)?(?: the)?)\s+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if name in CONFERENCE_ALIASES:
        return CONFERENCE_ALIASES[name]
    for alias, record in CONFERENCE_ALIASES.items():
        # Crossref can repeat an acronym at BOTH ends, e.g.
        # ICASSP 2025 - 2025 IEEE ... Processing (ICASSP).
        # Remove only this venue's complete acronym tokens, never arbitrary
        # words, so workshops and joint conferences remain distinct.
        candidate = name
        acronyms = {normalized(record[0]), normalized(record[1])}
        while True:
            previous = candidate
            for acronym in acronyms:
                candidate = candidate.removeprefix(acronym + " ").removesuffix(" " + acronym)
            if candidate == previous:
                break
        if candidate == alias:
            return record
    if re.fullmatch(r"advances in neural information processing systems \d+", name):
        return BY_KEY["nips"]
    return None


def string_definitions():
    return "\n".join(f"@String({key} = {{{short}}})" for key, short, _ in VENUES) + "\n"
