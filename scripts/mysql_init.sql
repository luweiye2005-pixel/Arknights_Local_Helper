-- Tables for arknights_helper (run after CREATE DATABASE)

CREATE TABLE IF NOT EXISTS meta (
  k VARCHAR(64) PRIMARY KEY,
  v JSON NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS themes (
  id VARCHAR(32) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  start_time BIGINT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS theme_difficulties (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  theme_id VARCHAR(32) NOT NULL,
  mode_difficulty VARCHAR(32) NOT NULL,
  grade INT NOT NULL DEFAULT 0,
  equivalent_grade INT NOT NULL DEFAULT 0,
  name VARCHAR(128) NOT NULL DEFAULT '',
  score_factor DOUBLE NULL,
  rule_desc TEXT NULL,
  color VARCHAR(32) NULL,
  sort_id INT NULL,
  UNIQUE KEY uk_theme_mode_grade (theme_id, mode_difficulty, grade),
  KEY idx_theme_eq (theme_id, equivalent_grade),
  CONSTRAINT fk_diff_theme FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS operators (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  rarity TINYINT NOT NULL DEFAULT 0,
  profession VARCHAR(32) NULL,
  profession_cn VARCHAR(32) NULL,
  sub_profession VARCHAR(64) NULL,
  position VARCHAR(16) NULL,
  appellation VARCHAR(128) NULL,
  description TEXT NULL,
  KEY idx_op_name (name),
  KEY idx_op_rarity (rarity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS operator_phases (
  operator_id VARCHAR(64) NOT NULL,
  elite TINYINT NOT NULL,
  max_level INT NOT NULL DEFAULT 1,
  range_id VARCHAR(64) NULL,
  PRIMARY KEY (operator_id, elite),
  CONSTRAINT fk_phase_op FOREIGN KEY (operator_id) REFERENCES operators(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS operator_phase_stats (
  operator_id VARCHAR(64) NOT NULL,
  elite TINYINT NOT NULL,
  level INT NOT NULL,
  hp DOUBLE NOT NULL DEFAULT 0,
  atk DOUBLE NOT NULL DEFAULT 0,
  def_stat DOUBLE NOT NULL DEFAULT 0,
  res DOUBLE NOT NULL DEFAULT 0,
  aspd DOUBLE NOT NULL DEFAULT 100,
  base_attack_time DOUBLE NOT NULL DEFAULT 1,
  PRIMARY KEY (operator_id, elite, level),
  CONSTRAINT fk_pstats_op FOREIGN KEY (operator_id) REFERENCES operators(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS operator_favor_stats (
  operator_id VARCHAR(64) NOT NULL,
  favor_level INT NOT NULL,
  hp DOUBLE NOT NULL DEFAULT 0,
  atk DOUBLE NOT NULL DEFAULT 0,
  def_stat DOUBLE NOT NULL DEFAULT 0,
  PRIMARY KEY (operator_id, favor_level),
  CONSTRAINT fk_favor_op FOREIGN KEY (operator_id) REFERENCES operators(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS modules (
  id VARCHAR(64) PRIMARY KEY,
  operator_id VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  type_name VARCHAR(32) NULL,
  max_level INT NOT NULL DEFAULT 1,
  description TEXT NULL,
  KEY idx_mod_op (operator_id),
  CONSTRAINT fk_mod_op FOREIGN KEY (operator_id) REFERENCES operators(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS module_levels (
  module_id VARCHAR(64) NOT NULL,
  level INT NOT NULL,
  atk DOUBLE NOT NULL DEFAULT 0,
  atk_pct DOUBLE NOT NULL DEFAULT 0,
  hp DOUBLE NOT NULL DEFAULT 0,
  defense DOUBLE NOT NULL DEFAULT 0,
  attack_speed DOUBLE NOT NULL DEFAULT 0,
  PRIMARY KEY (module_id, level),
  CONSTRAINT fk_ml_mod FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS enemies (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  enemy_level VARCHAR(64) NULL,
  description TEXT NULL,
  damage_type VARCHAR(16) NULL,
  KEY idx_enemy_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS enemy_levels (
  enemy_id VARCHAR(64) NOT NULL,
  level_index INT NOT NULL,
  hp DOUBLE NOT NULL DEFAULT 0,
  atk DOUBLE NOT NULL DEFAULT 0,
  def_stat DOUBLE NOT NULL DEFAULT 0,
  magic_resistance DOUBLE NOT NULL DEFAULT 0,
  move_speed DOUBLE NOT NULL DEFAULT 0,
  attack_speed DOUBLE NOT NULL DEFAULT 0,
  range_radius DOUBLE NOT NULL DEFAULT 0,
  PRIMARY KEY (enemy_id, level_index),
  CONSTRAINT fk_el_enemy FOREIGN KEY (enemy_id) REFERENCES enemies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS theme_enemies (
  theme_id VARCHAR(32) NOT NULL,
  enemy_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (theme_id, enemy_id),
  KEY idx_te_enemy (enemy_id),
  CONSTRAINT fk_te_theme FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
  CONSTRAINT fk_te_enemy FOREIGN KEY (enemy_id) REFERENCES enemies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS difficulty_stat_mods (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  theme_id VARCHAR(32) NOT NULL,
  equivalent_grade INT NOT NULL DEFAULT 0,
  target VARCHAR(32) NOT NULL,
  attr VARCHAR(64) NOT NULL,
  value DOUBLE NOT NULL DEFAULT 0,
  op ENUM('add','mul') NOT NULL DEFAULT 'mul',
  note VARCHAR(255) NULL,
  UNIQUE KEY uk_diff_mod (theme_id, equivalent_grade, target, attr),
  KEY idx_diff_mod_lookup (theme_id, equivalent_grade),
  CONSTRAINT fk_dsm_theme FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS relics (
  id VARCHAR(64) PRIMARY KEY,
  theme_id VARCHAR(32) NOT NULL,
  name VARCHAR(128) NOT NULL,
  usage_text TEXT NULL,
  description TEXT NULL,
  icon_id VARCHAR(128) NULL,
  order_id VARCHAR(32) NULL,
  item_type VARCHAR(32) NULL,
  KEY idx_relic_name (name),
  KEY idx_relic_theme (theme_id),
  CONSTRAINT fk_relic_theme FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS relic_effects (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  relic_id VARCHAR(64) NOT NULL,
  target ENUM('operator','enemy') NOT NULL DEFAULT 'operator',
  attr VARCHAR(64) NOT NULL,
  value DOUBLE NOT NULL DEFAULT 0,
  source ENUM('parsed','manual') NOT NULL DEFAULT 'parsed',
  note VARCHAR(255) NULL,
  KEY idx_re_relic (relic_id),
  CONSTRAINT fk_re_relic FOREIGN KEY (relic_id) REFERENCES relics(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS relic_upgrade_groups (
  group_id VARCHAR(128) PRIMARY KEY,
  theme_id VARCHAR(32) NOT NULL,
  base_relic_id VARCHAR(64) NULL,
  KEY idx_rug_theme (theme_id),
  CONSTRAINT fk_rug_theme FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS relic_upgrade_steps (
  group_id VARCHAR(128) NOT NULL,
  equivalent_grade_min INT NOT NULL DEFAULT 0,
  relic_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (group_id, equivalent_grade_min),
  KEY idx_rus_relic (relic_id),
  CONSTRAINT fk_rus_group FOREIGN KEY (group_id) REFERENCES relic_upgrade_groups(group_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
