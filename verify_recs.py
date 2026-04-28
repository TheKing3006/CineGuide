from profile_builder import get_personalized_picks
import json

picks = get_personalized_picks(5)
print(f"Total Picks: {len(picks)}")
no_poster = 0
for p in picks:
    has_poster = bool(p.get("poster"))
    if not has_poster: no_poster += 1
    print(f"- {p['title']} ({p['year']})")
    print(f"  Reason: {p.get('reason')}")
    print(f"  Poster: {'YES' if has_poster else 'NO'}")

print(f"\nNon-poster count: {no_poster}")
if no_poster <= 1:
    print("SUCCESS: Poster constraint met.")
else:
    print("FAILURE: Too many non-poster movies.")
