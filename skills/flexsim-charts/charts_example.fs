// Example charts file for dashboard_png.py. Works on any model: it picks objects by class.
// Each //@chart block makes ONE chart on the export dashboard `dash`. Name -> <name>.png.
// Templates: maintree().find("project/exec/globals/ChartTemplateDefinitions/<Group>/<Name>")
//   (Content/AverageWIPBar, Content/CompositeWIPVsTime, State/StateBar, Output/..., Staytime/...).
// Composite templates use the groups InputObjects/OutputObjects instead of Objects.

//@chart processor_states 420 370
treenode ch = function_s(dash, "createGraphWindow", maintree().find("project/exec/globals/ChartTemplateDefinitions/State/StateBar"), 1, 420, 370);
setname(ch, "Processor states");
treenode rc = getvarnode(ch, "replacements");
Group grp = rc.subnodes["Objects"].value;
for (int i = 1; i <= model().subnodes.length; i++) {
	treenode n = model().subnodes[i];
	if (getdatatype(n) == DATATYPE_OBJECT && isclasstype(n, "Processor")) grp.addMember(n);
}
treenode st = model().find("Tools/StateTables/StateTable1");
if (!objectexists(st)) st = Tools.create("StateTable", "Default");
rc.subnodes["StateTable"].value = st;
function_s(ch, "onApply");

//@chart queue_content 420 370
treenode ch = function_s(dash, "createGraphWindow", maintree().find("project/exec/globals/ChartTemplateDefinitions/Content/AverageWIPBar"), 1, 420, 370);
setname(ch, "Average queue content");
treenode rc = getvarnode(ch, "replacements");
Group grp = rc.subnodes["Objects"].value;
for (int i = 1; i <= model().subnodes.length; i++) {
	treenode n = model().subnodes[i];
	if (getdatatype(n) == DATATYPE_OBJECT && isclasstype(n, "Queue")) grp.addMember(n);
}
function_s(ch, "onApply");
// bar charts hide rows with value 0 unless this is set
treenode sz = getvarnode(function_s(ch, "getChart"), "barSettings").find("showZeroColumns");
if (objectexists(sz)) sz.value = 1;
