class MPSlipMapPanel:
    def click_position_text(self):
        if self.click_pos is None:
            return None
        if self.click_pos == self.last_click_pos:
            return self.last_click_position_text

        if self.click_pos == self.last_click_pos_used_for_text:
            return self.last_click_position_text

        terrain_height = None
        terrain_height_str = "?"
        if self.state.elevation != "None":
            terrain_height = self.state.ElevationMap.GetElevation(self.click_pos[0], self.click_pos[1])
            if terrain_height is not None:
                terrain_height_str = ' %.1fm' % (terrain_height,)

        newtext = 'Click: %.8f %.8f %s (%s %s) (%s)' % (
            self.click_pos[0],
            self.click_pos[1],
            terrain_height_str,
            mp_util.degrees_to_dms(self.click_pos[0]),
            mp_util.degrees_to_dms(self.click_pos[1]),
            mp_util.latlon_to_grid(self.click_pos)
        )

        if self.last_click_pos is not None:
            # provide information about the differences between the
            # previous click position:
            distance = mp_util.gps_distance(self.last_click_pos[0], self.last_click_pos[1],
                                            self.click_pos[0], self.click_pos[1])
            bearing = mp_util.gps_bearing(self.last_click_pos[0], self.last_click_pos[1],
                                            self.click_pos[0], self.click_pos[1])
            newtext += '  Distance: %.3fm %.3fnm Bearing %.1f' % (distance, distance*0.000539957, bearing)
            if terrain_height == "?":
                self.last_terrain_height = None
            else:
                if self.last_terrain_height is not None:
                    delta = terrain_height - self.last_terrain_height
                    newtext += " (height %f)" % (delta, )
        self.last_terrain_height = terrain_height
        self.last_click_pos_used_for_text = self.click_pos

        self.last_click_position_text = newtext

        return newtext
