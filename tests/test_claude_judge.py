from types import SimpleNamespace

import pytest

from arc.evals.claude_judge import ClaudeJudge
from arc.types import Outcome


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.messages = self

    def create(self, model, max_tokens, messages):
        self.prompts.append(messages[0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(text=self.replies.pop(0))])


def _outcome(text="Seats: Free has 3, Pro 25."):
    o = Outcome("c1", "r1-prod", "seats", "answer", 0, 0, 1)
    o.transcript = [
        {"role": "customer", "text": "how many seats? my email is a.b@example.com"},
        {"role": "agent", "text": text, "kind": "answer", "events": [{"type": "answer", "article": "storage-limits"}]},
    ]
    return o


def test_claude_judge_parses_scores_and_redacts():
    fc = FakeClient(['{"resolved": 0.9, "hallucinated": 0.05}', "sorry, I can't", '{"resolved": 2, "hallucinated": -1}'])
    j = ClaudeJudge(client=fc, model="test")
    s = j.score([_outcome(), _outcome(), _outcome()], ["free", "free", "pro"])
    assert s.resolved[0] == pytest.approx(0.9) and s.resolved[2] == 1.0 and s.hallucinated[2] == 0.0
    assert s.resolved[1] == pytest.approx((0.9 + 1.0) / 2)  # unreadable reply: the judge's own average
    assert "example.com" not in fc.prompts[0] and "free plan" in fc.prompts[0]
    assert "(none)" not in fc.prompts[0]  # the article the agent answered from is in the prompt
