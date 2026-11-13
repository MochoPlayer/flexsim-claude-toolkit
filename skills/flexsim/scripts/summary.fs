// summary.fs: compact description of a FlexSim model.
// Writes: units, global tables, then per object: class, position, ports, labels,
// changed numeric variables, and code that differs from a fresh object of the same class.
fileopen("{{OUT}}", "w");
treenode units = model().find("Tools/ModelUnits");
fpt("# UNITS time=" + getnodestr(units.find("Time/Name")) + " length=" + getnodestr(units.find("Length/Name"))); fpr();

// ---------- global tables
treenode gts = model().find("Tools/GlobalTables");
if (objectexists(gts)) {
	for (int g = 1; g <= gts.subnodes.length; g++) {
		treenode gt = gts.subnodes[g];
		Table t = Table(gt.name);
		fpt("# TABLE " + gt.name + " rows=" + string.fromNum(t.numRows) + " cols=" + string.fromNum(t.numCols)); fpr();
		string hdr = "row";
		for (int c = 1; c <= t.numCols; c++) hdr += " | " + t.getColHeader(c);
		fpt(hdr); fpr();
		for (int r = 1; r <= t.numRows; r++) {
			string line = t.getRowHeader(r);
			for (int c = 1; c <= t.numCols; c++) {
				treenode cell = t.cell(r, c);
				if (getdatatype(cell) == DATATYPE_STRING) line += " | " + getnodestr(cell);
				else line += " | " + string.fromNum(getnodenum(cell), 4);
			}
			fpt(line); fpr();
		}
	}
}

// ---------- objects
Array clsNames = ["Combiner", "Separator", "MultiProcessor", "Processor", "Source", "Sink", "Queue",
	"Operator", "Transporter", "Dispatcher", "NetworkNode", "Conveyor", "Rack", "BasicFR", "BasicTE"];
treenode m = model();
Array objs = [];
for (int i = 1; i <= m.subnodes.length; i++) objs.push(m.subnodes[i]);
for (int i = 1; i <= objs.length; i++) {
	treenode n = objs[i];
	if (getdatatype(n) != DATATYPE_OBJECT) continue;
	Object o = n;
	string cls = "?";
	treenode cl = n.find(">classes");
	treenode clsNode = 0;
	if (objectexists(cl) && cl.subnodes.length > 0) {
		clsNode = cl.first.value;
		if (objectexists(clsNode)) cls = clsNode.name;
	}
	if (o.name == "FlexsimModelFloor" || o.name == "DefaultNavigator") continue;
	fpr();
	fpt("## " + o.name + " (" + cls + ") at x=" + string.fromNum(o.location.x, 2) + " y=" + string.fromNum(o.location.y, 2)
		+ " size=" + string.fromNum(o.size.x, 2) + "x" + string.fromNum(o.size.y, 2)); fpr();
	string ports = "  in:";
	for (int k = 1; k <= o.inObjects.length; k++) ports += " " + string.fromNum(k) + "=" + o.inObjects[k].name;
	ports += " | out:";
	for (int k = 1; k <= o.outObjects.length; k++) ports += " " + string.fromNum(k) + "=" + o.outObjects[k].name;
	ports += " | center:";
	for (int k = 1; k <= o.centerObjects.length; k++) ports += " " + string.fromNum(k) + "=" + o.centerObjects[k].name;
	fpt(ports); fpr();
	treenode labs = n.find(">labels");
	if (objectexists(labs) && labs.subnodes.length > 0) {
		string ls = "  labels:";
		for (int k = 1; k <= labs.subnodes.length; k++) {
			treenode l = labs.subnodes[k];
			if (getdatatype(l) == DATATYPE_STRING) ls += " " + l.name + "=\"" + getnodestr(l) + "\"";
			else ls += " " + l.name + "=" + string.fromNum(getnodenum(l), 4);
		}
		fpt(ls); fpr();
	}
	// fresh object of the same class, to show only what was changed
	treenode ref = 0;
	if (objectexists(clsNode)) ref = createinstance(clsNode, model());
	treenode vars = n.find(">variables");
	if (!objectexists(vars)) { if (objectexists(ref)) destroyobject(ref); continue; }
	string nums = "  changed vars:";
	for (int k = 1; k <= vars.subnodes.length; k++) {
		treenode v = vars.subnodes[k];
		treenode rv = 0;
		if (objectexists(ref)) rv = ref.find(">variables/" + v.name);
		int dt = getdatatype(v);
		if (dt == DATATYPE_NUMBER) {
			if (!objectexists(rv) || getnodenum(rv) != getnodenum(v))
				nums += " " + v.name + "=" + string.fromNum(getnodenum(v), 4);
		} else if (dt == DATATYPE_STRING) {
			if (!objectexists(rv) || getnodestr(rv) != getnodestr(v)) {
				fpt("  code " + v.name + ":"); fpr();
				fpt("    " + getnodestr(v).replace("\r", "").replace("\n", "\n    ")); fpr();
			}
		}
		// small subtrees (component list, schedules, sequences): print up to 2 levels
		if (v.subnodes.length > 0 && v.subnodes.length <= 60) {
			string sub = "";
			for (int a = 1; a <= v.subnodes.length; a++) {
				treenode s = v.subnodes[a];
				string val = "";
				if (getdatatype(s) == DATATYPE_NUMBER) val = "=" + string.fromNum(getnodenum(s), 4);
				else if (getdatatype(s) == DATATYPE_STRING) val = "=\"" + getnodestr(s) + "\"";
				string inner = "";
				for (int b = 1; b <= s.subnodes.length && b <= 20; b++) {
					treenode s2 = s.subnodes[b];
					inner += " " + s2.name;
					if (getdatatype(s2) == DATATYPE_NUMBER) inner += "=" + string.fromNum(getnodenum(s2), 4);
					else if (getdatatype(s2) == DATATYPE_STRING) inner += "=\"" + getnodestr(s2) + "\"";
				}
				if (inner != "") inner = " {" + inner + " }";
				sub += "\n      " + s.name + val + inner;
			}
			int refsame = 0;
			if (objectexists(rv) && rv.subnodes.length == v.subnodes.length && v.subnodes.length == 0) refsame = 1;
			if (!refsame && v.name != "timetables" && v.name != "collisionspheres") { fpt("  " + v.name + ":" + sub); fpr(); }
		}
	}
	fpt(nums); fpr();
	if (objectexists(ref)) destroyobject(ref);
}
fpr(); fpt("# END"); fpr();
fileclose();
