package com.nhlbet.slates;

import java.time.LocalDate;

public record SlateDto(
        long gameId,
        LocalDate gameDate,
        String homeTeam,
        String awayTeam,
        double pHomeWin,
        double pAwayWin,
        String bestHomeBook,
        Integer bestHomeAmerican,
        Double bestHomeDecimal,
        String bestAwayBook,
        Integer bestAwayAmerican,
        Double bestAwayDecimal
) {}