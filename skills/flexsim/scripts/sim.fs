// sim.fs: reset, run {{HOURS}} hours ({{REPS}} replications), write statistics per object.
// Any model time unit: the stop time is {{HOURS}} hours converted to model time.
// Output (tab separated):
//   REP  obj  class  input  output  staytime_avg  content_avg  content_max  then state=time pairs
// Last line per replication: END rep t=<model time reached>
// If t is less than the stop time, the model ran out of events (something is blocked or finished).
double STOP = convert(getmodelunit(START_TIME) + {{HOURS}} * 3600, FS_DATETIME, MODEL_TIME);
fileopen("{{OUT}}", "w");
fpt("# time unit: " + getnodestr(model().find("Tools/ModelUnits/Time/Name")) + "  stop=" + string.fromNum(STOP)); fpr();
fileclose();
for (int rep = 1; rep <= {{REPS}}; rep++) {
	resetmodel();
	stoptime(STOP);
	runfunction(1);
	fileopen("{{OUT}}", "a");
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
		string line = "REP" + string.fromNum(rep) + "\t" + o.name + "\t" + cls
			+ "\tin=" + string.fromNum(o.stats.input.value)
			+ "\tout=" + string.fromNum(o.stats.output.value)
			+ "\tstay_avg=" + string.fromNum(o.stats.staytime.average, 2)
			+ "\tcontent_avg=" + string.fromNum(o.stats.content.average, 3)
			+ "\tcontent_max=" + string.fromNum(o.stats.content.maximum);
		Table prof = o.stats.state().profile;
		for (int r = 1; r <= prof.numRows; r++) {
			double v = prof[r][2];
			if (v > 0) line += "\t" + prof[r][1] + "=" + string.fromNum(v, 1);
		}
		fpt(line); fpr();
	}
	fpt("END rep" + string.fromNum(rep) + " t=" + string.fromNum(time(), 1)); fpr();
	fileclose();
}
