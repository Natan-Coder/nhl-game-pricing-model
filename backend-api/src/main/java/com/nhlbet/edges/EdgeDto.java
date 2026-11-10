package com.nhlbet.edges;


public record EdgeDto(
        long id,
        long gameId,
        String book,
        String market,
        String outcome,
        int americanOdds,
        double impliedProb,
        double modelProb,
        double edge,
        double kellyFraction,
        double suggestedStake
) {}