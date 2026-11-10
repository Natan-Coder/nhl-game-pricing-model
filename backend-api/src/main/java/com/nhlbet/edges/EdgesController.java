package com.nhlbet.edges;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class EdgesController {
    private final JdbcTemplate jdbc;
    public EdgesController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping("/health")
    public String health() { return "OK"; }

    @GetMapping("/edges")
    public List<EdgeDto> edges(
            @RequestParam(defaultValue = "0.0") double minEdge,
            @RequestParam(defaultValue = "moneyline") String market
    ) {
        String sql = """
            SELECT id, game_id, book, market, outcome, american_odds, implied_prob, model_prob,
            edge, kelly_fraction, suggested_stake
            FROM edges
            WHERE market = ? AND edge >= ?
            ORDER BY edge DESC, computed_at DESC
            LIMIT 50    
        """;
        return jdbc.query(sql, (rs, row) -> new EdgeDto(
                rs.getLong("id"),
                rs.getLong("game_id"),
                rs.getString("book"),
                rs.getString("market"),
                rs.getString("outcome"),
                rs.getInt("american_odds"),
                rs.getDouble("implied_prob"),
                rs.getDouble("model_prob"),
                rs.getDouble("edge"),
                rs.getDouble("kelly_fraction"),
                rs.getDouble("suggested_stake")
        ), market, minEdge);
    }
}