"""Deterministic venue aliases and explicit reference-style abbreviations."""

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
            "IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops",
        ],
    ),
    (
        "TCSVT",
        "IEEE Trans. Circuits Syst. Video Technol.",
        [
            "IEEE Transactions on Circuits and Systems for Video Technology",
            "IEEE Trans. Circuit Syst. Video Technol.",
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
        "IV",
        "IV",
        ["IEEE Intelligent Vehicles Symposium", "Intelligent Vehicles Symposium", "IEEE IV"],
    ),
    (
        "ITSC",
        "ITSC",
        [
            "IEEE International Conference on Intelligent Transportation Systems",
            "International Conference on Intelligent Transportation Systems",
            "IEEE Intelligent Transportation Systems Conference",
        ],
    ),
    ("ICPRS", "ICPRS", ["International Conference on Pattern Recognition Systems"]),
    ("ICVES", "ICVES", ["IEEE International Conference on Vehicular Electronics and Safety"]),
    ("ICDL", "ICDL", ["IEEE International Conference on Development and Learning"]),
    (
        "ICTC",
        "ICTC",
        ["International Conference on Information and Communication Technology Convergence"],
    ),
    (
        "ICECET",
        "ICECET",
        ["International Conference on Electrical, Computer and Energy Technologies"],
    ),
    (
        "NNICE",
        "NNICE",
        ["International Conference on Neural Networks, Information and Communication Engineering"],
    ),
    ("INDIN", "INDIN", ["IEEE International Conference on Industrial Informatics"]),
    ("SECON", "SECON", ["IEEE International Conference on Sensing, Communication, and Networking"]),
    ("ISAS", "ISAS", ["International Symposium on Autonomous Systems"]),
    ("CCC", "CCC", ["Chinese Control Conference"]),
    ("RadarConf", "RadarConf", ["IEEE Radar Conference"]),
    ("VTCSpring", "VTC-Spring", ["IEEE Vehicular Technology Conference Spring"]),
    ("VTCFall", "VTC-Fall", ["IEEE Vehicular Technology Conference Fall"]),
    (
        "ICONIP",
        "ICONIP",
        [
            "International Conference on Neural Information Processing",
            "Neural Information Processing",
        ],
    ),
    (
        "ECCVW",
        "ECCVW",
        [
            "Computer Vision ECCV Workshops",
            "European Conference on Computer Vision Workshops",
            "ECCV Workshops",
        ],
    ),
    ("GeMiC", "GeMiC", ["German Microwave Conference"]),
    ("CRV", "CRV", ["Conference on Computer and Robot Vision"]),
    (
        "MCSoC",
        "MCSoC",
        ["IEEE International Symposium on Embedded Multicore/Many-core Systems-on-Chip"],
    ),
    ("ICCRI", "ICCRI", ["International Conference on Control, Robotics and Informatics"]),
    ("ROBIO", "ROBIO", ["IEEE International Conference on Robotics and Biomimetics"]),
    (
        "VCIP",
        "VCIP",
        ["IEEE International Conference on Visual Communications and Image Processing"],
    ),
    (
        "CSCWD",
        "CSCWD",
        ["International Conference on Computer Supported Cooperative Work in Design"],
    ),
    ("IECON", "IECON", ["Annual Conference of the IEEE Industrial Electronics Society"]),
    ("ICAUS", "ICAUS", ["International Conference on Autonomous Unmanned Systems"]),
    ("ECSA", "ECSA", ["International Electronic Conference on Sensors and Applications"]),
    ("CoRL", "CoRL", ["Conference on Robot Learning"]),
    ("EuRAD", "EuRAD", ["European Radar Conference"]),
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
    (
        "IJCAI",
        "IJCAI",
        [
            "International Joint Conference on Artificial Intelligence",
            "Proceedings of the Thirty-ThirdInternational Joint Conference on Artificial Intelligence",
        ],
    ),
    ("PR", "Pattern Recognit.", ["Pattern Recognition"]),
    ("ACCESS", "IEEE Access", []),
    ("RAL", "IEEE Robot. Autom. Lett.", ["IEEE Robotics and Automation Letters", "IEEE RA-L"]),
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
            "IEEE/CVF International Conference on Computer Vision Workshop",
            "IEEE International Conference on Computer Vision Workshop",
            "IEEE/CVF International Conference on Computer Vision (ICCV) Workshops",
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
    (
        "TNNLS",
        "IEEE Trans. Neural Netw. Learn. Syst.",
        ["IEEE Transactions on Neural Networks and Learning Systems"],
    ),
    ("ESWA", "Expert Syst. Appl.", ["Expert Systems with Applications"]),
    ("NN", "Neural Netw.", ["Neural Networks"]),
    (
        "ISPRSARCH",
        "ISPRS Archives",
        [
            "The International Archives of the Photogrammetry, Remote Sensing and Spatial Information Sciences",
            "Int. Arch. Photogramm. Remote Sens. Spatial Inf. Sci.",
        ],
    ),
    ("AIReview", "Artif. Intell. Rev.", ["Artificial Intelligence Review"]),
    (
        "IJPEM",
        "Int. J. Precis. Eng. Manuf.",
        ["International Journal of Precision Engineering and Manufacturing"],
    ),
]

CONFERENCE_TITLES = {
    "ACCV": "Proc. Asian Conf. Comput. Vis. (ACCV)",
    "AAAI": "Proc. AAAI Conf. Artif. Intell. (AAAI)",
    "CVPRW": "Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. Workshops (CVPRW)",
    "CVPR": "Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. (CVPR)",
    "ICCV": "Proc. IEEE/CVF Int. Conf. Comput. Vis. (ICCV)",
    "ECCV": "Proc. Eur. Conf. Comput. Vis. (ECCV)",
    "NIPS": "Adv. Neural Inf. Process. Syst. (NeurIPS)",
    "ICPR": "Proc. Int. Conf. Pattern Recognit. (ICPR)",
    "BMVC": "Proc. Brit. Mach. Vis. Conf. (BMVC)",
    "ACMMM": "Proc. ACM Int. Conf. Multimedia (ACM MM)",
    "ICME": "Proc. IEEE Int. Conf. Multimedia Expo (ICME)",
    "ICASSP": "Proc. IEEE Int. Conf. Acoust., Speech Signal Process. (ICASSP)",
    "ICIP": "Proc. IEEE Int. Conf. Image Process. (ICIP)",
    "ICLR": "Int. Conf. Learn. Represent. (ICLR)",
    "IROS": "Proc. IEEE/RSJ Int. Conf. Intell. Robots Syst. (IROS)",
    "ICRA": "Proc. IEEE Int. Conf. Robot. Autom. (ICRA)",
    "IJCAI": "Proc. Int. Joint Conf. Artif. Intell. (IJCAI)",
    "WACV": "Proc. IEEE/CVF Winter Conf. Appl. Comput. Vis. (WACV)",
    "EDGE": "Proc. ACM/IEEE Symp. Edge Comput. (EDGE)",
    "ICCVW": "Proc. IEEE/CVF Int. Conf. Comput. Vis. Workshops (ICCVW)",
    "IV": "Proc. IEEE Intell. Veh. Symp. (IV)",
    "ITSC": "Proc. IEEE Int. Conf. Intell. Transp. Syst. (ITSC)",
    "ICPRS": "Proc. Int. Conf. Pattern Recognit. Syst. (ICPRS)",
    "ICVES": "Proc. IEEE Int. Conf. Veh. Electron. Saf. (ICVES)",
    "ICDL": "Proc. IEEE Int. Conf. Develop. Learn. (ICDL)",
    "ICTC": "Proc. Int. Conf. Inf. Commun. Technol. Converg. (ICTC)",
    "ICECET": "Proc. Int. Conf. Electr., Comput. Energy Technol. (ICECET)",
    "NNICE": "Proc. Int. Conf. Neural Netw., Inf. Commun. Eng. (NNICE)",
    "INDIN": "Proc. IEEE Int. Conf. Ind. Informat. (INDIN)",
    "SECON": "Proc. IEEE Int. Conf. Sens., Commun. Netw. (SECON)",
    "ISAS": "Proc. Int. Symp. Auton. Syst. (ISAS)",
    "CCC": "Proc. Chin. Control Conf. (CCC)",
    "RadarConf": "Proc. IEEE Radar Conf. (RadarConf)",
    "VTCSpring": "Proc. IEEE Veh. Technol. Conf. (VTC-Spring)",
    "VTCFall": "Proc. IEEE Veh. Technol. Conf. (VTC-Fall)",
    "ICONIP": "Proc. Int. Conf. Neural Inf. Process. (ICONIP)",
    "ECCVW": "Proc. Eur. Conf. Comput. Vis. Workshops (ECCVW)",
    "GeMiC": "Proc. German Microw. Conf. (GeMiC)",
    "CRV": "Proc. Conf. Comput. Robot Vis. (CRV)",
    "MCSoC": "Proc. IEEE Int. Symp. Embedded Multicore/Many-core Syst.-on-Chip (MCSoC)",
    "ICCRI": "Proc. Int. Conf. Control, Robot. Informat. (ICCRI)",
    "ROBIO": "Proc. IEEE Int. Conf. Robot. Biomimetics (ROBIO)",
    "VCIP": "Proc. IEEE Int. Conf. Vis. Commun. Image Process. (VCIP)",
    "CSCWD": "Proc. Int. Conf. Comput. Supported Cooperative Work Design (CSCWD)",
    "IECON": "Proc. Annu. Conf. IEEE Ind. Electron. Soc. (IECON)",
    "ICAUS": "Proc. Int. Conf. Auton. Unmanned Syst. (ICAUS)",
    "ECSA": "Proc. Int. Electron. Conf. Sensors Appl. (ECSA)",
    "CoRL": "Proc. Conf. Robot Learn. (CoRL)",
    "EuRAD": "Proc. Eur. Radar Conf. (EuRAD)",
}

# Keep former acronym-only outputs as aliases for saved jobs and old exports.
CONFERENCE_ACRONYMS = {
    key: {normalized(key), normalized(short)}
    for key, short, _ in VENUES
    if key in CONFERENCE_TITLES
}
VENUES = [
    (key, CONFERENCE_TITLES.get(key, short), [short, *aliases]) for key, short, aliases in VENUES
]

CONFERENCES = set(CONFERENCE_TITLES)
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
    name = re.sub(r"^(?:(?:proceedings|procedings|proc)(?: of)?(?: the)?|the)\s+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Explicit year-bearing conference acronyms; keep the VTC season and year.
    vtc = re.fullmatch(
        r"(?:(?:ieee )?(?:vehicular technology conference|veh technol conf) )?vtc((?:19|20)\d{2}) (spring|fall)",
        name,
    )
    if vtc:
        return (
            "VTCSpring" if vtc[2] == "spring" else "VTCFall",
            f"Proc. IEEE Veh. Technol. Conf. (VTC{vtc[1]}-{vtc[2].title()})",
        )
    name = re.sub(r"\bradarconf(?:\d{2}|(?:19|20)\d{2})\b", "radarconf", name)
    # SECON's edition adds 'Annual' before IEEE; this is an explicit alias.
    name = (
        name.removeprefix("annual ")
        if name.startswith("annual ieee international conference on sensing ")
        else name
    )
    if name in CONFERENCE_ALIASES:
        return CONFERENCE_ALIASES[name]
    for alias, record in CONFERENCE_ALIASES.items():
        # Crossref can repeat an acronym at BOTH ends, e.g.
        # ICASSP 2025 - 2025 IEEE ... Processing (ICASSP).
        # Remove only this venue's complete acronym tokens, never arbitrary
        # words, so workshops and joint conferences remain distinct.
        candidate = name
        acronyms = CONFERENCE_ACRONYMS[record[0]]
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
