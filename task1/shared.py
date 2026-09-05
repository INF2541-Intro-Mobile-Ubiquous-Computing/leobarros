import constants

def scheduleSendQuestionTimer(self):
    self.provider.schedule_timer(
        "communication",
        self.provider.current_time() + constants.SEND_QUESTION_INTERVAL
    )

def scheduleMobilityTimer(self):
    self.provider.schedule_timer(
        "mobility",
        self.provider.current_time() + constants.MOBILITY_INTERVAL
    )