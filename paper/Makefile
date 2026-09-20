# Build the paper. Figures are regenerated from committed evidence artifacts
# first, so a figure can never drift from the experiment record it illustrates.

PAPER := main
PY    := python3

.PHONY: all figures clean distclean

all: $(PAPER).pdf

figures:
	cd .. && $(PY) paper/make_figures.py

$(PAPER).pdf: $(PAPER).tex refs.bib figures
	pdflatex -interaction=nonstopmode -halt-on-error $(PAPER).tex
	bibtex $(PAPER)
	pdflatex -interaction=nonstopmode -halt-on-error $(PAPER).tex
	pdflatex -interaction=nonstopmode -halt-on-error $(PAPER).tex
	@echo
	@grep -c "undefined" $(PAPER).log > /dev/null && \
	  grep -n "Warning.*undefined\|Citation.*undefined\|Reference.*undefined" $(PAPER).log || \
	  echo "no undefined references"

clean:
	rm -f $(PAPER).aux $(PAPER).bbl $(PAPER).blg $(PAPER).log $(PAPER).out

distclean: clean
	rm -f $(PAPER).pdf
