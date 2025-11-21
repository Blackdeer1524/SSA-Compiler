.PHONY: graph cfg ir open-graph

INPUT ?= input.txt
DOT_FILE ?= graph.dot
SVG_FILE ?= graph.svg
IR_FILE ?= ir.txt

cfg:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE)

graph: cfg
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

open-graph: graph
	firefox $(SVG_FILE)

ir:
	python main.py --input $(INPUT) --dump-ir $(IR_FILE)