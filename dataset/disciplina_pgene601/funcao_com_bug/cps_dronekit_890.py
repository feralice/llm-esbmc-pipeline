class Vehicle:
    @property
    def is_armable(self):
        """
        Returns ``True`` if the vehicle is ready to arm, false otherwise (``Boolean``).

        This attribute wraps a number of pre-arm checks, ensuring that the vehicle has booted,
        has a good GPS fix, and that the EKF pre-arm is complete.
        """
        # check that mode is not INITIALSING
        # check that we have a GPS fix
        # check that EKF pre-arm is complete
        return self.mode != 'INITIALISING' and self.gps_0.fix_type > 1 and self._ekf_predposhorizabs
