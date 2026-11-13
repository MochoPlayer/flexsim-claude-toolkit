// dump.fs: raw tree dump below one node ({{PATH}}, e.g. "Processor1" or "Tools/GlobalTables").
// Prints name, value and the object attributes variables/labels/spatial. Max depth 12.
fileopen("{{OUT}}", "w");
treenode root = model();
if ("{{PATH}}" != "") root = model().find("{{PATH}}");
if (!objectexists(root)) { fpt("not found: {{PATH}}"); fpr(); fileclose(); return 0; }
Array stack = [root];
Array depth = [0];
while (stack.length > 0) {
	treenode n = stack.pop();
	int d = depth.pop();
	string ind = "";
	for (int i = 0; i < d; i++) ind += "  ";
	string line = ind + n.name;
	int dt = getdatatype(n);
	if (dt == DATATYPE_NUMBER) line += " = " + string.fromNum(getnodenum(n), 6);
	else if (dt == DATATYPE_STRING) line += " = \"" + getnodestr(n).replace("\r", "") + "\"";
	else if (dt == DATATYPE_OBJECT) line += " [obj]";
	fpt(line); fpr();
	if (d > 12) continue;
	Array kids = [];
	for (int i = 1; i <= n.subnodes.length; i++) kids.push(n.subnodes[i]);
	if (dt == DATATYPE_OBJECT) {
		Array attrs = ["variables", "labels", "spatial"];
		for (int j = 1; j <= attrs.length; j++) {
			treenode a = n.find(">" + attrs[j]);
			if (objectexists(a)) kids.push(a);
		}
	}
	for (int i = kids.length; i >= 1; i--) { stack.push(kids[i]); depth.push(d + 1); }
}
fileclose();
