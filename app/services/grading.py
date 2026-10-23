"""服务端判分：只依据题目版本保存的 options、answers 与 grading_policy。"""

MAX_ANSWER_LENGTH = 255
_CHOICE_ERROR = {"recognition": "meaning", "context": "context"}


class InvalidAnswer(ValueError):
    pass


def normalize(question, raw):
    """把原始答案转为可比较、可存储的标准形式；格式不合法时抛出 InvalidAnswer。

    空答案合法，按未作答判错。
    """
    if not isinstance(raw, str):
        raise InvalidAnswer("answer 必须是字符串")
    if question["skill_type"] == "spelling":
        policy = question["grading_policy"]
        value = raw.strip() if policy["trim"] else raw
        if not policy["case_sensitive"]:
            value = value.casefold()
    else:
        value = raw.strip()
        if value and value not in {option["id"] for option in question["options"]}:
            raise InvalidAnswer("answer 必须是选项 id 之一")
    if len(value) > MAX_ANSWER_LENGTH:
        raise InvalidAnswer(f"answer 超过 {MAX_ANSWER_LENGTH} 字符")
    return value


def grade(question, normalized):
    """返回 (is_correct, error_type)。error_type 只表示题型与答案能支持的类别。"""
    if not normalized.strip():
        return False, "unanswered"
    if question["skill_type"] == "spelling":
        accepted = {normalize(question, answer) for answer in question["answers"]["accepted"]}
        return (True, None) if normalized in accepted else (False, "spelling")
    if normalized == question["answers"]["option_id"]:
        return True, None
    return False, _CHOICE_ERROR[question["skill_type"]]


def correct_answer(question):
    """作答后展示的标准答案。"""
    if question["skill_type"] == "spelling":
        accepted = question["answers"]["accepted"]
        return {"text": accepted[0], "accepted": accepted}
    option_id = question["answers"]["option_id"]
    text = next(option["text"] for option in question["options"] if option["id"] == option_id)
    return {"option_id": option_id, "text": text}
