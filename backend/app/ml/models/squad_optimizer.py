"""Genetic algorithm powered squad optimizer."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class SquadOptimizer:
    budget: float
    squad_size: int = 15
    min_batsmen: int = 5
    min_bowlers: int = 5
    min_all_rounders: int = 2
    min_wicket_keepers: int = 1
    max_overseas: int = 4

    def optimize_squad(
        self,
        available_players: List[Dict],
        population_size: int = 50,
        generations: int = 30,
    ) -> Dict:
        population = [
            self._create_random_valid_squad(available_players)
            for _ in range(population_size)
        ]
        population = [squad for squad in population if squad]

        best_squad: List[int] = []
        best_score = float("-inf")

        for _ in range(generations):
            fitness_scores = [
                self._calculate_fitness(squad, available_players) for squad in population
            ]
            if not fitness_scores:
                break
            idx = int(np.argmax(fitness_scores))
            if fitness_scores[idx] > best_score:
                best_score = fitness_scores[idx]
                best_squad = population[idx]

            selected = self._tournament_selection(population, fitness_scores)
            offspring: List[List[int]] = []
            for i in range(0, len(selected), 2):
                if i + 1 < len(selected):
                    child_a, child_b = self._crossover(selected[i], selected[i + 1])
                    offspring.extend([child_a, child_b])
            population = selected + [self._mutate(child, available_players) for child in offspring]

        return self._format_result(best_squad, available_players, best_score)

    def _create_random_valid_squad(self, players: List[Dict]) -> List[int]:
        squad: List[int] = []
        total_cost = 0.0
        role_counts = {"batsman": 0, "bowler": 0, "all_rounder": 0, "wicket_keeper": 0}
        overseas = 0
        shuffled = players.copy()
        random.shuffle(shuffled)
        for player in shuffled:
            if len(squad) >= self.squad_size:
                break
            pid = int(player["player_id"])
            cost = float(player.get("auction_price", 0))
            role = player.get("role", "batsman")
            is_overseas = player.get("country") != "South Africa"
            if (total_cost + cost <= self.budget) and (pid not in squad):
                if is_overseas and overseas >= self.max_overseas:
                    continue
                squad.append(pid)
                total_cost += cost
                role_counts[role] = role_counts.get(role, 0) + 1
                if is_overseas:
                    overseas += 1
        if (
            role_counts.get("batsman", 0) >= self.min_batsmen
            and role_counts.get("bowler", 0) >= self.min_bowlers
            and role_counts.get("all_rounder", 0) >= self.min_all_rounders
            and role_counts.get("wicket_keeper", 0) >= self.min_wicket_keepers
        ):
            return squad
        return []

    def _calculate_fitness(self, squad: List[int], players: List[Dict]) -> float:
        if not squad:
            return float("-inf")
        selected = [player for player in players if int(player["player_id"]) in squad]
        cost = sum(float(player.get("auction_price", 0)) for player in selected)
        if cost > self.budget:
            return float("-inf")
        batting = sum(player.get("batting_impact", 0) for player in selected)
        bowling = sum(player.get("bowling_impact", 0) for player in selected)
        caps = sum(player.get("international_caps", 0) for player in selected)
        ages = [player.get("age", 0) for player in selected]
        diversity = np.std(ages) if ages else 0
        return batting * 0.3 + bowling * 0.3 + caps * 0.02 + diversity * 2

    def _tournament_selection(self, population: List[List[int]], scores: List[float]) -> List[List[int]]:
        selected: List[List[int]] = []
        for _ in range(len(population) // 2):
            idx = random.sample(range(len(population)), k=min(3, len(population)))
            best = max(idx, key=lambda i: scores[i])
            selected.append(population[best])
        return selected

    def _crossover(self, parent_a: List[int], parent_b: List[int]) -> tuple[List[int], List[int]]:
        if not parent_a or not parent_b:
            return parent_a, parent_b
        point = random.randint(1, min(len(parent_a), len(parent_b)) - 1)
        child_a = parent_a[:point] + [p for p in parent_b if p not in parent_a[:point]]
        child_b = parent_b[:point] + [p for p in parent_a if p not in parent_b[:point]]
        return child_a[: self.squad_size], child_b[: self.squad_size]

    def _mutate(self, squad: List[int], players: List[Dict]) -> List[int]:
        if not squad or random.random() > 0.2:
            return squad
        mutated = squad.copy()
        idx = random.randrange(len(mutated))
        mutated.pop(idx)
        available = [p for p in players if int(p["player_id"]) not in mutated]
        if available:
            mutated.append(int(random.choice(available)["player_id"]))
        return mutated

    def _format_result(self, squad: List[int], players: List[Dict], score: float) -> Dict:
        selected = [player for player in players if int(player["player_id"]) in squad]
        total_cost = sum(float(player.get("auction_price", 0)) for player in selected)
        return {
            "squad": selected,
            "total_cost": total_cost,
            "remaining_budget": self.budget - total_cost,
            "fitness_score": score,
            "squad_size": len(selected),
            "overseas_players": len([p for p in selected if p.get("country") != "South Africa"]),
        }
