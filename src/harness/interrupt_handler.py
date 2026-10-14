class InterruptHandler:
    @staticmethod
    def parse_cicd_approval(answer: str) -> bool:
        match answer.strip().lower():
            case "yes":
                return True
            case "no":
                return False
            case _:
                raise ValueError('Please answer "yes" or "no".')
