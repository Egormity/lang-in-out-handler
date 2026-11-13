"""Text composition shared by live documents and saved recording sessions."""


def flowing_text(parts):
    """Join successive recognition chunks without inserting spaces inside CJK text."""
    result = []
    previous = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if previous:
            left_cjk = "\u3000" <= previous[-1] <= "\u9fff" or "\uac00" <= previous[-1] <= "\ud7af"
            right_cjk = "\u3000" <= part[0] <= "\u9fff" or "\uac00" <= part[0] <= "\ud7af"
            if not (left_cjk and right_cjk) and part[0] not in ".,!?;:)]}、。！？":
                result.append(" ")
        result.append(part)
        previous = part
    return "".join(result)
