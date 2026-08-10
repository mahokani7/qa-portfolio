class RaiTFilter:
    @staticmethod
    def check_pass_fail(final_score, target_score, scores, cutoffs, mode='hybrid'):
        """
        mode: 'simple', 'weight', 'cutoff', 'hybrid'
        """
        pass_score = final_score >= target_score
        pass_cutoff = True
        cutoff_fails = []

        # 커트라인 검증이 필요한 모드인 경우
        if mode in ['cutoff', 'hybrid']:
            for metric, cutoff_val in cutoffs.items():
                if scores.get(metric, 0.0) < cutoff_val:
                    pass_cutoff = False
                    cutoff_fails.append(f"{metric}(기준:{cutoff_val}/실제:{scores[metric]})")

        # 최종 상태 판정
        if mode == 'simple':
            status = "Pass" if pass_score else "Fail"
        elif mode == 'weight':
            status = "Pass" if pass_score else "Fail"
        elif mode == 'cutoff':
            status = "Pass" if (pass_score and pass_cutoff) else "Fail"
        else: # hybrid
            status = "Pass" if (pass_score and pass_cutoff) else "Fail"

        return {
            "status": status,
            "final_score": round(final_score, 2),
            "pass_score": pass_score,
            "pass_cutoff": pass_cutoff,
            "cutoff_fails": cutoff_fails
        }