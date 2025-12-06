.PHONY: graph cfg ir open-graph

INPUT ?= input.txt
DOT_FILE ?= graph.dot
SVG_FILE ?= graph.svg
IR_FILE ?= ir.txt

cfg:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) 

graph: cfg
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-O1:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-sccp --disable-licm --disable-dce --disable-block-cleanup 
	
graph-O1: cfg-O1
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-sccp:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-licm --disable-dce --disable-block-cleanup 
	
graph-sccp: cfg-sccp
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-dce:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-licm --disable-sccp --disable-block-cleanup 
	
graph-dce: cfg-dce
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)
	
cfg-no-ssa:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-ssa 
	
graph-no-ssa: cfg-no-ssa
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-licm:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-sccp --disable-dce --disable-block-cleanup 
	
graph-licm: cfg-licm
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

open-graph: graph
	firefox $(SVG_FILE)

show-dot:
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

ir:
	python main.py --input $(INPUT) --dump-ir $(IR_FILE)