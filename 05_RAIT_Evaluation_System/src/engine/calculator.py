import numpy as np

class RaiTCalculator:
    @staticmethod
    def calculate_simple_average(scores):
        """8개 지표의 단순 산술 평균 계산"""
        return float(np.mean(list(scores.values())))

    @staticmethod
    def calculate_weighted_average(scores, weights):
        """RaiT 가중치 방식 공식 적용"""
        total_score_weight = sum(scores[k] * weights.get(k, 1.0) for k in scores.keys())
        total_weight = sum(weights.get(k, 1.0) for k in scores.keys())
        
        return float(total_score_weight / total_weight) if total_weight > 0 else 0.0