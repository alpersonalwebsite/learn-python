# No dependencies and no virtualenv: every target is python3 plus git, both of which you already
# have if you are reading a document about setting up a Python project.

.PHONY: check check-samples check-gitignore check-links

check: check-samples check-gitignore check-links

# ast.parse every python block, bash -n every shell block.
check-samples:
	python3 scripts/check_samples.py

# The .gitignore this repository RECOMMENDS, and the one it uses, both put to git check-ignore.
check-gitignore:
	python3 scripts/check_gitignore_advice.py

# Every relative link and #anchor resolves.
check-links:
	python3 scripts/check_links.py
