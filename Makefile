COVERAGE=coverage
MYPY=mypy
PIP=python -m pip
PYLINT=pylint
RM=rm -rf
SOURCES_ANALYSIS=gatherer scraper controller maintenance test tests.py
SOURCES_COVERAGE=gatherer,test
TEST=tests.py
TWINE=twine

.PHONY: all
all: coverage mypy pylint

.PHONY: release
release: test mypy pylint clean build tag push upload

.PHONY: setup
setup:
	$(PIP) install -r requirements.txt

.PHONY: setup_release
setup_release:
	$(PIP) install -r requirements-release.txt

.PHONY: setup_agent
setup_agent:
	$(PIP) install -r requirements-agent.txt

.PHONY: setup_jenkins
setup_jenkins:
	$(PIP) install -r requirements-jenkins.txt

.PHONY: setup_daemon
setup_daemon:
	$(PIP) install -r requirements-daemon.txt

.PHONY: setup_analysis
setup_analysis:
	$(PIP) install -r requirements-analysis.txt

.PHONY: setup_test
setup_test:
	$(PIP) install -r requirements-test.txt

.PHONY: setup_docs
setup_docs:
	$(PIP) install -r requirements-docs.txt

.PHONY: install
install:
	$(PIP) install .

.PHONY: pylint
pylint:
	$(PYLINT) $(SOURCES_ANALYSIS) \
		--exit-zero --reports=n \
		--msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
		-d duplicate-code

.PHONY: mypy
mypy:
	$(MYPY) $(SOURCES_ANALYSIS) \
		--cobertura-xml-report mypy-report \
		--junit-xml mypy-report/TEST-junit.xml \
		--no-incremental --show-traceback

.PHONY: mypy_html
mypy_html:
	$(MYPY) $(SOURCES_ANALYSIS) \
		--html-report mypy-report \
		--cobertura-xml-report mypy-report \
		--junit-xml mypy-report/TEST-junit.xml \
		--no-incremental --show-traceback

.PHONY: test
test:
	python $(TEST) --no-output

.PHONY: coverage
coverage:
	$(COVERAGE) run --source=$(SOURCES_COVERAGE) $(TEST)
	$(COVERAGE) report -m
	$(COVERAGE) xml -i -o test-reports/cobertura.xml

# Version of the coverage target that does not write JUnit/cobertura XML output
.PHONY: cover
cover:
	$(COVERAGE) run --source=$(SOURCES_COVERAGE) $(TEST) --no-output
	$(COVERAGE) report -m

.PHONY: get_version
get_version: get_toml_version get_init_version get_sonar_version get_citation_version get_changelog_version get_docs_version
	if [ "${TOML_VERSION}" != "${INIT_VERSION}" ] || [ "${TOML_VERSION}" != "${SONAR_VERSION}" ] || [ "${TOML_VERSION}" != "${CITATION_VERSION}" ] || [ "${TOML_VERSION}" != "${CHANGELOG_VERSION}" ] || [ "${TOML_VERSION}" != "${DOCS_VERSION}" ]; then \
		echo "Version mismatch"; \
		exit 1; \
	fi
	$(eval VERSION=$(TOML_VERSION))

.PHONY: get_init_version
get_init_version:
	$(eval INIT_VERSION=v$(shell grep __version__ gatherer/__init__.py | sed -E "s/__version__ = .([0-9.]+)./\\1/"))
	$(info Version in __init__.py: $(INIT_VERSION))
	if [ -z "${INIT_VERSION}" ]; then \
		echo "Could not parse version"; \
		exit 1; \
	fi

.PHONY: get_toml_version
get_toml_version:
	$(eval TOML_VERSION=v$(shell grep "^version" pyproject.toml | sed -E "s/version = .([0-9.]+)./\\1/"))
	$(info Version in pyproject.toml: $(TOML_VERSION))

.PHONY: get_sonar_version
get_sonar_version:
	$(eval SONAR_VERSION=v$(shell grep projectVersion sonar-project.properties | cut -d= -f2))
	$(info Version in sonar-project.properties: $(SONAR_VERSION))

.PHONY: get_citation_version
get_citation_version:
	$(eval CITATION_VERSION=v$(shell grep "^version:" CITATION.cff | cut -d' ' -f2))
	$(info Version in CITATION.cff: $(CITATION_VERSION))

.PHONY: get_changelog_version
get_changelog_version:
	$(eval CHANGELOG_VERSION=v$(shell grep "^## \[[0-9]\+\.[0-9]\+\.[0-9]\+\]" CHANGELOG.md | head -n 1 | sed -E "s/## \[([0-9]+\.[0-9]+\.[0-9]+)\].*/\1/"))
	$(info Version in CHANGELOG.md: $(CHANGELOG_VERSION))

.PHONY: get_docs_version
get_docs_version:
	$(eval DOCS_VERSION=v$(shell grep "^release" doc/source/conf.py | sed -E "s/release = .([0-9.]+)./\\1/"))
	$(info Version in doc/source/conf.py: $(DOCS_VERSION))

.PHONY: tag
tag: get_version
	git tag $(VERSION)

.PHONY: build
build:
	python -m build

.PHONY: push
push: get_version
	git push origin $(VERSION)

.PHONY: upload
upload:
	$(TWINE) upload dist/*

.PHONY: docs
docs:
	make html -C doc

.PHONY: clean
clean:
	# Unit tests and coverage
	$(RM) .coverage htmlcov/ test-reports/
	# Typing coverage and Pylint
	$(RM) .mypy_cache mypy-report/ pylint-report.txt
	# Importer distribution
	$(RM) data_vcsdev_to_dev.json importerjson.jar lib/ README.TXT
	# Repositories and retrieved files
	$(RM) dropins/*/ project-git-repos/
	# maintenance/filter-sourcecode.sh
	$(RM) bfg.jar filter.txt
	# Pip and distribution
	$(RM) src/ build/ dist/ gros-gatherer.egg-info/
