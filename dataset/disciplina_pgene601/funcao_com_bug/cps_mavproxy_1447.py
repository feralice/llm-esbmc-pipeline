class BatteryModule:
    def cmd_bat(self, args):
        '''show battery levels'''
        print("Flight battery:   %u%%" % self.battery_level[0])
        for id in range(9):
            if self.numcells(id) != 0 and id in self.voltage_level:
                print("Bat%u %.2f V/cell for %u cells %.1fA %.2f%%" % (id+1,
                                                                        self.per_cell[id],
                                                                        self.numcells(id),
                                                                        self.current_battery[id],
                                                                        self.battery_level[id]))
