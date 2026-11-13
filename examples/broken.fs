// broken.fs: a script with one real-world mistake, for flexsim-bisect.
// FlexSim runs none of it and gives no error text. Line 13 is the bug:
// Model.find() returns a treenode, so ".location" needs a cast to Object first.
fileopen("{{OUT}}", "w");
fpt("objects in the model:"); fpr();
for (int i = 1; i <= model().subnodes.length; i++) {
	treenode n = model().subnodes[i];
	if (getdatatype(n) == DATATYPE_OBJECT) { fpt("  " + n.name); fpr(); }
}
Object pro = Model.find("Processor1");
fpt("processor at x=" + string.fromNum(pro.location.x)); fpr();
double ct = getvarnum(pro, "cycletime");
fpt("queue at x=" + string.fromNum(Model.find("Queue1").location.x)); fpr();
fpt("cycle time=" + string.fromNum(ct)); fpr();
fileclose();
