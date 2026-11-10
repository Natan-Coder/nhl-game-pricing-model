buildscript {
    dependencies {
        classpath("org.postgresql:postgresql:42.7.3")
        classpath("org.flywaydb:flyway-database-postgresql:10.8.1")
    }
}

plugins {
    id("org.springframework.boot") version "3.3.3"
    id("io.spring.dependency-management") version "1.1.5"
    id("org.flywaydb.flyway") version "10.8.1"
    java
}


group = "com.nhlbet"
version = "0.0.1-SNAPSHOT"
java.sourceCompatibility = JavaVersion.VERSION_21


repositories { mavenCentral() }


dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-jdbc")
    implementation("org.flywaydb:flyway-core")
    implementation("org.flywaydb:flyway-database-postgresql")
    runtimeOnly("org.postgresql:postgresql:42.7.3")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}


tasks.withType<Test> { useJUnitPlatform() }

// Workaround for older IntelliJ Kotlin DSL sync expecting this task:
//tasks.register("prepareKotlinBuildScriptModel") {
//    group = "ide"
//    description = "Stub to satisfy older IntelliJ Kotlin DSL sync."
//}


// Flyway configuration
flyway {
    // Use FLYWAY_URL if set (JDBC format), otherwise fall back to default
    // Added prepareThreshold=0 to disable prepared statements (fixes PostgreSQL 17.6 compatibility)
    url = System.getenv("FLYWAY_URL") ?: "jdbc:postgresql://localhost:5432/nhl_betting?prepareThreshold=0"
    // User and password are included in FLYWAY_URL, so these are only for fallback
    user = System.getenv("DB_USER") ?: "postgres"
    password = System.getenv("DB_PASSWORD") ?: "postgres"
    locations = arrayOf("filesystem:../infra/db/migrations")
    baselineOnMigrate = true
    validateOnMigrate = true
}
