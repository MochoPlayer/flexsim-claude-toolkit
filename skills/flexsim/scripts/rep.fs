// rep.fs: ONE replication with seed {{SEED}}, run {{HOURS}} hours, stats per object (default script of `fs.py reps`).
// Seeding: after resetmodel(), randinit(s, seed * 1000 + s + 1) for random streams 0-99.
// Any model time unit: the stop time is {{HOURS}} hours converted to model time.
// Output (tab separated): SEED, then one OBJ line per object, then END t=<model time reached> stop=<stop time>.
double STOP = convert(getmodelunit(START_TIME) + {{HOURS}} * 3600, FS_DATETIME, MODEL_TIME);
resetmodel();
for (int s = 0; s <= 99; s++) randinit(s, {{SEED}} * 1000 + s + 1);
stoptime(STOP);
runfunction(1);
fileopen("{{OUT}}", "w");
fpt("SEED " + string.fromNum({{SEED}})); fpr();
treenode m = model();
for (int i = 1; i <= m.subnodes.length; i++) {
	treenode n = m.subnodes[i];
	if (getdatatype(n) != DATATYPE_OBJECT) continue;
	treenode cl = n.find(">classes");
	if (!objectexists(cl) || cl.subnodes.length == 0) continue;
	treenode cn = cl.first.value;
	string cls = "?";
	if (objectexists(cn)) cls = cn.name;
	if (cls == "VisualTool" || cls == "AStarNavigator" || n.name == "DefaultNavigator") continue;
	Object o = n;
	string line = "OBJ\t" + o.name + "\t" + cls
		+ "\tin=" + string.fromNum(o.stats.input.value)
		+ "\tout=" + string.fromNum(o.stats.output.value)
		+ "\tstay_avg=" + string.fromNum(o.stats.staytime.average, 2)
		+ "\tcontent_avg=" + string.fromNum(o.stats.content.average, 3);
	Table prof = o.stats.state().profile;
	for (int r = 1; r <= prof.numRows; r++) {
		double v = prof[r][2];
		if (v > 0) line += "\t" + prof[r][1] + "=" + string.fromNum(v, 1);
	}
	fpt(line); fpr();
}
fpt("END t=" + string.fromNum(time(), 1) + " stop=" + string.fromNum(STOP, 1)); fpr();
fileclose();
