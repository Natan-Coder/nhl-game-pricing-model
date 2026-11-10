package com.nhlbet.slates;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.sql.Date;
import java.time.LocalDate;
import java.util.List;

@RestController
public class SlatesController {
    private final JdbcTemplate jdbc;
    public SlatesController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping("/slates")
    public List<SlateDto> slates(@RequestParam(required = false) String date) {
        LocalDate d = (date == null || date.isBlank()) ? LocalDate.now() : LocalDate.parse(date);
        String sql = """
            SELECT game_id, game_date. home_team, away_team,
                   p_home_win, p_away_win,
                   best_home_book, best_home_american, best_home_decimal,
                   best_away_book, best_away_american, best_away_decimal
            FROM game_slate
            WHERE game_date = ?
            ORDER BY game_id
        """;
        return jdbc.query(sql, (rs, row) -> new SlateDto(
                rs.getLong("game_id"),
                rs.getDate("game_date").toLocalDate(),
                rs.getString("home_team"),
                rs.getString("away_team"),
                rs.getDouble("p_home_win"),
                rs.getDouble("p_away_win"),
                rs.getString("best_home_book"),
                (Integer) rs.getObject("best_home_american"),
                (Double) rs.getObject("best_home_decimal"),
                rs.getString("best_away_book"),
                (Integer) rs.getObject("best_away_american"),
                (Double) rs.getObject("best_away_decimal")
        ), Date.valueOf(d));
    }
}