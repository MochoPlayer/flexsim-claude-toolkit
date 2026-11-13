// build_demo.fs: builds the demo model Source -> Queue -> Processor -> Sink on an empty model and saves it.
// Run: python -I -X utf8 skills/flexsim/fs.py new examples/build_demo.fs
// Then copy <work>/demo.fsm to examples/demo.fsm (the run prints the saved path).
// Model time unit: seconds (default). Arrivals: exponential, mean 30 s. Processing: 25 s, fixed.
fileopen("{{OUT}}", "w"); fpt("build start"); fpr(); fileclose();

// "fixedresources/..." matters: library().find("?Sink") returns the Process Flow Sink activity.
Object src = createinstance(library().find("fixedresources/Source"), model());
Object que = createinstance(library().find("fixedresources/Queue"), model());
Object pro = createinstance(library().find("fixedresources/Processor"), model());
Object snk = createinstance(library().find("fixedresources/Sink"), model());
setname(src, "Source1"); setname(que, "Queue1"); setname(pro, "Processor1"); setname(snk, "Sink1");
src.location = Vec3(0, 0, 0);
que.location = Vec3(4, 0, 0);
pro.location = Vec3(8, 0, 0);
snk.location = Vec3(12, 0, 0);
contextdragconnection(src, que, "A");
contextdragconnection(que, pro, "A");
contextdragconnection(pro, snk, "A");

// arrivals: code field, exponential with mean 30 s on random stream 1
treenode ia = getvarnode(src, "interarrivaltime");
ia.dataType = DATATYPE_STRING;
setnodestr(ia, "Object current = ownerobject(c);\nObject item = param(1);\nreturn exponential(0, 30, 1);\n");
switch_flexscript(ia, 1);
buildnodeflexscript(ia);

// processing time: plain number (25 s); experiments change it
treenode ct = getvarnode(pro, "cycletime");
ct.dataType = DATATYPE_NUMBER;
setnodenum(ct, 25);

// label read by the example experiment (a scenario can change labels too)
assertlabel(pro, "Shift", DATATYPE_NUMBER).value = 1;

resetmodel();
cmdsavetree(model(), "{{WORK}}/demo.fsm");
fileopen("{{OUT}}", "a"); fpt("saved {{WORK}}/demo.fsm"); fpr(); fileclose();
