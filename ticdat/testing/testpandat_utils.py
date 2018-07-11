import unittest
from ticdat.pandatfactory import PanDatFactory
from ticdat.utils import DataFrame, numericish
from ticdat.testing.ticdattestutils import fail_to_debugger, flagged_as_run_alone, netflowPandasData
from ticdat.testing.ticdattestutils import netflowSchema, copy_to_pandas_with_reset, dietSchema, netflowData
from ticdat.testing.ticdattestutils import addNetflowForeignKeys
from ticdat.ticdatfactory import TicDatFactory
import itertools
from math import isnan

#uncomment decorator to drop into debugger for assertTrue, assertFalse failures
#@fail_to_debugger
class TestUtils(unittest.TestCase):
    canRun = False
    def testSimple(self):
        if not self.canRun:
            return
        pdf = PanDatFactory(**netflowSchema())
        _dat = netflowPandasData()
        dat = pdf.PanDat(**{t:getattr(_dat, t) for t in pdf.all_tables})
        self.assertTrue(pdf.good_pan_dat_object(dat))

        dat2 = pdf.copy_pan_dat(dat)
        self.assertTrue(pdf._same_data(dat, dat2))
        self.assertTrue(pdf.good_pan_dat_object(dat2))
        delattr(dat2, "nodes")
        msg = []
        self.assertFalse(pdf.good_pan_dat_object(dat2, msg.append))
        self.assertTrue(msg[-1] == "nodes not an attribute.")

        dat3 = pdf.copy_pan_dat(dat)
        dat3.cost.drop("commodity", axis=1, inplace=True)
        self.assertFalse(pdf.good_pan_dat_object(dat3, msg.append))
        self.assertTrue("The following are (table, field) pairs missing from the data" in msg[-1])

        dat4 = pdf.copy_pan_dat(dat)
        dat4.cost["cost"] += 1
        self.assertFalse(pdf._same_data(dat, dat4))

    def testDataTypes(self):
        if not self.canRun:
            return
        tdf = TicDatFactory(**dietSchema())
        pdf = PanDatFactory(**dietSchema())

        ticdat = tdf.TicDat()
        ticdat.foods["a"] = 12
        ticdat.foods["b"] = None
        ticdat.categories["1"] = {"maxNutrition":100, "minNutrition":40}
        ticdat.categories["2"] = [10,20]
        for f, p in itertools.product(ticdat.foods, ticdat.categories):
            ticdat.nutritionQuantities[f,p] = 5
        ticdat.nutritionQuantities['a', 2] = 12

        pandat = pdf.copy_pan_dat(copy_to_pandas_with_reset(tdf, ticdat))

        self.assertFalse(pdf.find_data_type_failures(pandat))

        pdf = PanDatFactory(**dietSchema())
        pdf.set_data_type("foods", "cost", nullable=False)
        pdf.set_data_type("nutritionQuantities", "qty", min=5, inclusive_min=False, max=12, inclusive_max=True)
        failed = pdf.find_data_type_failures(pandat)
        self.assertTrue(set(failed) == {('foods', 'cost'), ('nutritionQuantities', 'qty')})
        self.assertTrue(set(failed['foods', 'cost']["name"]) == {'b'})
        self.assertTrue(set({(v["food"], v["category"])
                             for v in failed['nutritionQuantities', 'qty'].T.to_dict().values()}) ==
                            {('b', '1'), ('a', '2'), ('a', '1'), ('b', '2')})

        tdf = TicDatFactory(**netflowSchema())
        tdf.enable_foreign_key_links()
        addNetflowForeignKeys(tdf)
        pdf = PanDatFactory(**netflowSchema())
        ticdat = tdf.copy_tic_dat(netflowData())
        for n in ticdat.nodes["Detroit"].arcs_source:
            ticdat.arcs["Detroit", n] = n
        pandat = pdf.copy_pan_dat(copy_to_pandas_with_reset(tdf, ticdat))
        self.assertFalse(pdf.find_data_type_failures(pandat))

        pdf = PanDatFactory(**netflowSchema())
        pdf.set_data_type("arcs", "capacity", strings_allowed="*")
        self.assertFalse(pdf.find_data_type_failures(pandat))

        pdf = PanDatFactory(**netflowSchema())
        pdf.set_data_type("arcs", "capacity", strings_allowed=["Boston", "Seattle", "lumberjack"])
        failed = pdf.find_data_type_failures(pandat)
        self.assertTrue(set(failed) == {('arcs', 'capacity')})
        self.assertTrue(set({(v["source"], v["destination"])
                             for v in failed['arcs', 'capacity'].T.to_dict().values()}) == {("Detroit", "New York")})

    def testDataPredicates(self):
        if not self.canRun:
            return
        tdf = TicDatFactory(**dietSchema())
        pdf = PanDatFactory(**dietSchema())

        ticdat = tdf.TicDat()
        ticdat.foods["a"] = 12
        ticdat.foods["b"] = None
        ticdat.categories["1"] = {"maxNutrition":100, "minNutrition":40}
        ticdat.categories["2"] = [21,20]
        for f, p in itertools.product(ticdat.foods, ticdat.categories):
            ticdat.nutritionQuantities[f,p] = 5
        ticdat.nutritionQuantities['a', 2] = 12

        pandat = pdf.copy_pan_dat(copy_to_pandas_with_reset(tdf, ticdat))

        self.assertFalse(pdf.find_data_row_failures(pandat))

        pdf = PanDatFactory(**dietSchema())
        pdf.add_data_row_predicate("foods", lambda row: numericish(row["cost"]) and not isnan(row["cost"]), "cost")
        good_qty = lambda qty :  numericish(qty) and 5 < qty <= 12
        pdf.add_data_row_predicate("nutritionQuantities", lambda row: good_qty(row["qty"]), "qty")
        pdf.add_data_row_predicate("categories",
                                   lambda row: all(map(numericish, [row["minNutrition"], row["maxNutrition"]]))
                                               and row["maxNutrition"] >= row["minNutrition"],
                                   "minmax")
        failed = pdf.find_data_row_failures(pandat)
        self.assertTrue(set(failed) == {('foods', 'cost'), ('nutritionQuantities', 'qty'), ('categories', 'minmax')})
        self.assertTrue(set(failed['foods', 'cost']["name"]) == {'b'})
        self.assertTrue(set({(v["food"], v["category"])
                             for v in failed['nutritionQuantities', 'qty'].T.to_dict().values()}) ==
                            {('b', '1'), ('a', '2'), ('a', '1'), ('b', '2')})
        self.assertTrue(set(failed['categories', 'minmax']["name"]) == {'2'})

        tdf = TicDatFactory(**netflowSchema())
        tdf.enable_foreign_key_links()
        addNetflowForeignKeys(tdf)
        pdf = PanDatFactory(**netflowSchema())
        ticdat = tdf.copy_tic_dat(netflowData())
        for n in ticdat.nodes["Detroit"].arcs_source:
            ticdat.arcs["Detroit", n] = n
        pandat = pdf.copy_pan_dat(copy_to_pandas_with_reset(tdf, ticdat))
        self.assertFalse(pdf.find_data_row_failures(pandat))

        pdf = PanDatFactory(**netflowSchema())
        pdf.add_data_row_predicate("arcs", lambda row: True, "capacity")
        self.assertFalse(pdf.find_data_row_failures(pandat))

        pdf = PanDatFactory(**netflowSchema())
        good_capacity = lambda capacity: numericish(capacity) or capacity in ["Boston", "Seattle", "lumberjack"]
        pdf.add_data_row_predicate("arcs", lambda row: good_capacity(row["capacity"]), "capacity")
        failed = pdf.find_data_row_failures(pandat)
        self.assertTrue(set(failed) == {('arcs', 'capacity')})
        self.assertTrue(set({(v["source"], v["destination"])
                             for v in failed['arcs', 'capacity'].T.to_dict().values()}) == {("Detroit", "New York")})

    def testXToMany(self):
        input_schema = PanDatFactory (roster = [["Name"],["Grade", "Arrival Inning", "Departure Inning",
                                                          "Min Innings Played", "Max Innings Played"]],
                                      positions = [["Position"],["Position Importance", "Position Group",
                                                                 "Consecutive Innings Only"]],
                                      innings = [["Inning"],["Inning Group"]],
                                      position_constraints = [["Position Group", "Inning Group", "Grade"],
                                                              ["Min Players", "Max Players"]])
        input_schema.add_foreign_key("position_constraints", "roster", ["Grade", "Grade"])
        input_schema.add_foreign_key("position_constraints", "positions", ["Position Group", "Position Group"])
        input_schema.add_foreign_key("position_constraints", "innings", ["Inning Group", "Inning Group"])

        self.assertTrue({fk.cardinality for fk in input_schema.foreign_keys} == {"many-to-many"})

        tdf = TicDatFactory(**input_schema.schema())
        dat = tdf.TicDat()
        for i,p in enumerate(["bob", "joe", "fred", "alice", "lisa", "joean", "ginny"]):
            dat.roster[p]["Grade"] = (i%3)+1
        dat.roster["dummy"]["Grade"]  = "whatevers"
        for i,p in enumerate(["pitcher", "catcher", "1b", "2b", "ss", "3b", "lf", "cf", "rf"]):
            dat.positions[p]["Position Group"] = "PG %s"%((i%4)+1)
        for i in range(1, 10):
            dat.innings[i]["Inning Group"] = "before stretch" if i < 7 else "after stretch"
        dat.innings[0] ={}
        for pg, ig, g in itertools.product(["PG %s"%i for i in range(1,5)], ["before stretch", "after stretch"],
                                           [1, 2, 3]):
            dat.position_constraints[pg, ig, g] = {}

        orig_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        self.assertFalse(input_schema.find_foreign_key_failures(orig_pan_dat))

        dat.position_constraints["no", "no", "no"] = dat.position_constraints[1, 2, 3] = {}
        new_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        self.assertFalse(input_schema._same_data(orig_pan_dat, new_pan_dat))
        fk_fails = input_schema.find_foreign_key_failures(new_pan_dat)
        self.assertTrue({tuple(k)[:2]:len(v) for k,v in fk_fails.items()} ==
                        {('position_constraints', 'innings'): 2, ('position_constraints', 'positions'): 2,
                         ('position_constraints', 'roster'): 1})
        input_schema.remove_foreign_keys_failures(new_pan_dat)
        self.assertFalse(input_schema.find_foreign_key_failures(new_pan_dat))
        self.assertTrue(input_schema._same_data(orig_pan_dat, new_pan_dat))

        input_schema = PanDatFactory(table_one=[["One", "Two"], []],
                                     table_two=[["One"], ["Two"]])
        input_schema.add_foreign_key("table_two", "table_one", ["One", "One"])
        self.assertTrue({fk.cardinality for fk in input_schema.foreign_keys} == {"one-to-many"})

        tdf = TicDatFactory(**input_schema.schema())
        dat = tdf.TicDat(table_one = [[1,2], [3,4], [5,6], [7,8]], table_two = {1:2, 3:4, 5:6})

        orig_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        self.assertFalse(input_schema.find_foreign_key_failures(orig_pan_dat))
        dat.table_two[9]=10
        new_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        fk_fails = input_schema.find_foreign_key_failures(new_pan_dat)
        self.assertTrue({tuple(k)[:2]:len(v) for k,v in fk_fails.items()} == {('table_two', 'table_one'): 1})
        input_schema.remove_foreign_keys_failures(new_pan_dat)
        self.assertFalse(input_schema.find_foreign_key_failures(new_pan_dat))
        self.assertTrue(input_schema._same_data(orig_pan_dat, new_pan_dat))


    def testXToManyTwo(self):
        input_schema = PanDatFactory (parent = [["F1", "F2"],["F3"]], child_one = [["F1", "F2", "F3"], []],
                                      child_two = [["F1", "F2"], ["F3"]], child_three = [[],["F1", "F2", "F3"]])
        for t in ["child_one", "child_two", "child_three"]:
            input_schema.add_foreign_key(t, "parent", [["F1"]*2, ["F2"]*2, ["F3"]*2])
        self.assertTrue({fk.cardinality for fk in input_schema.foreign_keys} == {"one-to-one", "many-to-one"})

        rows =[[1,2,3], [1,2.1,3], [4,5,6],[4,5.1,6],[7,8,9]]
        tdf = TicDatFactory(**input_schema.schema())
        dat = tdf.TicDat(parent = rows, child_one = rows, child_two = rows, child_three=rows)
        self.assertTrue(all(len(getattr(dat, t)) == 5 for t in input_schema.all_tables))
        orig_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        self.assertFalse(input_schema.find_foreign_key_failures(orig_pan_dat))
        dat.child_one[1, 2, 4] = {}
        dat.child_two[1,2.2]=3
        dat.child_three.append([1,2,4])
        new_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        fk_fails = input_schema.find_foreign_key_failures(new_pan_dat)
        self.assertTrue(len(fk_fails) == 3)
        input_schema.remove_foreign_keys_failures(new_pan_dat)
        self.assertFalse(input_schema.find_foreign_key_failures(new_pan_dat))
        self.assertTrue(input_schema._same_data(orig_pan_dat, new_pan_dat))

        input_schema = PanDatFactory (parent = [["F1", "F2"],["F3"]], child_one = [["F1", "F2", "F3"], []],
                                      child_two = [["F1", "F2"], ["F3"]], child_three = [[],["F1", "F2", "F3"]])
        for t in ["child_one", "child_two", "child_three"]:
            input_schema.add_foreign_key(t, "parent", [["F1"]*2, ["F3"]*2])
        tdf = TicDatFactory(**input_schema.schema())
        dat = tdf.TicDat(parent=rows, child_one=rows, child_two=rows, child_three=rows)
        self.assertTrue(all(len(getattr(dat, t)) == 5 for t in input_schema.all_tables))
        orig_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        self.assertFalse(input_schema.find_foreign_key_failures(orig_pan_dat))
        dat.child_one[1, 2, 4] = {}
        dat.child_two[1,2.2]=4
        dat.child_three.append([1,2,4])
        new_pan_dat = input_schema.copy_pan_dat(copy_to_pandas_with_reset(tdf, dat))
        self.assertTrue(len(input_schema.find_foreign_key_failures(new_pan_dat)) == 3)
        input_schema.remove_foreign_keys_failures(new_pan_dat)
        self.assertFalse(input_schema.find_foreign_key_failures(new_pan_dat))
        self.assertTrue(input_schema._same_data(orig_pan_dat, new_pan_dat))


# Run the tests.
if __name__ == "__main__":
    if not DataFrame :
        print("!!!!!!!!!FAILING PANDAS UNIT TESTS DUE TO FAILURE TO LOAD PANDAS LIBRARIES!!!!!!!!")
    else:
        TestUtils.canRun = True
    unittest.main()