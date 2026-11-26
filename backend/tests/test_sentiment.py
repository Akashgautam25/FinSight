from app.services.sentiment_service import lexicon_sentiment


def test_positive_headline():
    r = lexicon_sentiment("Apple beats expectations and raises guidance as iPhone sales surge")
    assert r["sentiment"] == "positive" and r["compound_score"] > 0.3


def test_negative_headline():
    r = lexicon_sentiment("Shares plunge after company misses estimates and announces layoffs")
    assert r["sentiment"] == "negative" and r["compound_score"] < -0.3


def test_neutral_headline():
    r = lexicon_sentiment("Company to hold annual shareholder meeting on Tuesday")
    assert r["sentiment"] == "neutral"


def test_negation_flips_polarity():
    assert lexicon_sentiment("The results were not strong")["compound_score"] < 0


def test_probabilities_sum_to_one():
    r = lexicon_sentiment("Profit growth was robust despite rising costs and lawsuit concerns")
    assert abs(r["positive_score"] + r["negative_score"] + r["neutral_score"] - 1) < 1e-3


async def test_analyze_endpoint(auth_client):
    r = await auth_client.post("/api/v1/news/sentiment/analyze", json={"text": "Regulators open fraud investigation"})
    assert r.json()["sentiment"] == "negative"


async def test_news_endpoints_score_articles(auth_client):
    news = (await auth_client.get("/api/v1/news", params={"limit": 5})).json()
    assert news["total"] == 5 and all("sentiment" in a for a in news["articles"])
    summary = (await auth_client.get("/api/v1/news/AAPL/sentiment")).json()
    assert summary["news_count"] > 0
    assert abs(summary["positive_pct"] + summary["negative_pct"] + summary["neutral_pct"] - 100) < 0.5
