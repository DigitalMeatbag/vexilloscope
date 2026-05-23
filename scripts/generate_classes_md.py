import json

lines = [json.loads(l) for l in open('data/manifest/results.jsonl')]
cats = {}
for r in lines:
    cats.setdefault(r['category'], []).append(r['display_name'])

with open('CLASSES.md', 'w') as f:
    f.write('# Trained Classes\n\n')
    for cat, names in sorted(cats.items()):
        f.write(f'## {cat.title()} ({len(names)})\n\n')
        for n in sorted(names):
            f.write(f'- {n}\n')
        f.write('\n')

print(f"Written CLASSES.md — {len(lines)} classes across {len(cats)} categories")
