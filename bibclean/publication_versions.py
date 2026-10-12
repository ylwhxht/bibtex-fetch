"""Three explicitly requested publication corrections; no inferred upgrades.

Match both the original citation key and the complete normalized title. The
linked official records and the requested fields are recorded in export logs.
No author, title, DOI, page range, or publication date is guessed.
"""

from .abbreviations import CONFERENCE_TITLES
from .bibliography import normalized

PUBLICATION_VERSIONS = {
    "segment_anything": {
        "title": "Segment Anything",
        "source": "https://openaccess.thecvf.com/content/ICCV2023/html/Kirillov_Segment_Anything_ICCV_2023_paper.html",
        "fields": {
            "booktitle": CONFERENCE_TITLES["ICCV"],
            "year": "2023",
            "month": "October",
            "pages": "4015--4026",
        },
    },
    "li2023logonet": {
        "title": "LoGoNet: Towards Accurate 3D Object Detection With Local-to-Global Cross-Modal Fusion",
        "source": "https://openaccess.thecvf.com/content/CVPR2023/html/Li_LoGoNet_Towards_Accurate_3D_Object_Detection_With_Local-to-Global_Cross-Modal_Fusion_CVPR_2023_paper.html",
        "fields": {
            "booktitle": CONFERENCE_TITLES["CVPR"],
            "year": "2023",
            "month": "June",
            "pages": "17524--17534",
        },
    },
    "tent": {
        "title": "Tent: Fully Test-time Adaptation by Entropy Minimization",
        "source": "https://openreview.net/pdf?id=uXl3bZLkr3c",
        "fields": {"booktitle": CONFERENCE_TITLES["ICLR"], "year": "2021"},
    },
}


def publication_version(values, input_key=None):
    record = PUBLICATION_VERSIONS.get(input_key or values["ID"])
    if not record:
        return None, ""
    if normalized(values.get("title", "")) != normalized(record["title"]):
        return None, "publication correction key matched but title differs; left unchanged"
    return record, ""
