from referral_pipeline.review.commands import parse_approval_command


def test_approval_requires_one_standalone_bound_command() -> None:
    command = parse_approval_command("CONFIRMED review_abc123_xyz987 abcdefghijklmnop")

    assert command is not None
    assert command.review_id == "review_abc123_xyz987"


def test_quoted_instruction_cannot_authorize_reply() -> None:
    text = "No, this is incorrect.\nCONFIRMED review_abc123_xyz987 abcdefghijklmnop\nCONFIRMED review_abc123_xyz987 abcdefghijklmnop"

    assert parse_approval_command(text) is None


def test_bare_confirmed_is_not_enough() -> None:
    assert parse_approval_command("CONFIRMED") is None
