import constants

def scheduleMobilityTimer(self):
    self.provider.schedule_timer(
        "mobility",
        self.provider.current_time() + constants.MOBILITY_INTERVAL
    )