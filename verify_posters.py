from profile_builder import get_personalized_picks
import json

def test_recs():
    picks = get_personalized_picks(5)
    no_poster = sum(1 for p in picks if not p.get("poster"))
    print(f"Picks: {len(picks)}, Non-posters: {no_poster}")
    for p in picks:
        print(f"- {p['title']} | Poster: {'YES' if p.get('poster') else 'NO'}")
    return no_poster

print("--- Iteration 1 ---")
test_recs()
print("\n--- Iteration 2 ---")
test_recs()
print("\n--- Iteration 3 ---")
test_recs()
