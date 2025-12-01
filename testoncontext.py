from datetime import datetime

class HangoutContext:
    def __init__(self, relationship_level, casualness, recent_interaction,
                 mood_signal, time_of_day, day_of_week, response_history):
        """
        relationship_level: int (1–5) how close you are (1 = acquaintance, 5 = close friend)
        casualness: str ("spontaneous", "planned")
        recent_interaction: int (minutes since last chat or text)
        mood_signal: str ("positive", "neutral", "negative")
        time_of_day: datetime
        day_of_week: str ("Monday"..."Sunday")
        response_history: list of bools (True = accepted past hangouts)
        """
        self.relationship_level = relationship_level
        self.casualness = casualness
        self.recent_interaction = recent_interaction
        self.mood_signal = mood_signal
        self.time_of_day = time_of_day
        self.day_of_week = day_of_week
        self.response_history = response_history


class HangoutTimeEvaluator:
    def __init__(self):
        self.score_threshold = 0.6  # how "appropriate" the timing should feel

    def evaluate(self, context: HangoutContext):
        score = 0

        # Relationship level is most important
        score += (context.relationship_level / 5) * 0.4

        # Recent friendly interaction
        if context.recent_interaction < 180:
            score += 0.2  # within 3 hours
        elif context.recent_interaction < 1440:
            score += 0.1  # within a day

        # Mood tone from recent messages or vibe
        if context.mood_signal == "positive":
            score += 0.2
        elif context.mood_signal == "neutral":
            score += 0.1
        else:
            score -= 0.2

        # Time/day context
        if context.time_of_day.hour in range(16, 22):  # evening
            score += 0.15
        if context.day_of_week in ["Friday", "Saturday", "Sunday"]:
            score += 0.1

        # Past acceptance rate
        if context.response_history:
            acceptance_rate = sum(context.response_history) / len(context.response_history)
            score += acceptance_rate * 0.15

        # Clamp score between 0 and 1
        score = min(max(score, 0), 1)

        # Recommended notice time (based on closeness and casualness)
        if context.casualness == "spontaneous":
            if context.relationship_level >= 4:
                notice_time = "1–3 hours before"
            elif context.relationship_level >= 3:
                notice_time = "same day (4–6 hours before)"
            else:
                notice_time = "the day before"
        else:  # planned hangout
            if context.relationship_level >= 4:
                notice_time = "1–2 days ahead"
            elif context.relationship_level >= 3:
                notice_time = "2–3 days ahead"
            else:
                notice_time = "3–5 days ahead"

        recommendation = (
            f"Good time to plan a hangout ({context.casualness}). "
            f"Recommended notice: {notice_time}."
            if score >= self.score_threshold
            else f"Maybe wait or text casually first before suggesting a hangout."
        )

        return round(score, 2), recommendation


# Example usage
if __name__ == "__main__":
    context = HangoutContext(
        relationship_level=4,
        casualness="planned",
        recent_interaction=30,
        mood_signal="positive",
        time_of_day=datetime.now(),
        day_of_week="Saturday",
        response_history=[True, True, False, True]
    )

    evaluator = HangoutTimeEvaluator()
    score, advice = evaluator.evaluate(context)
    print(f"Hangout Appropriateness Score: {score} → {advice}")
