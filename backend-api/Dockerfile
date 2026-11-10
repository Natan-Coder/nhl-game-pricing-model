FROM  gradle:8-jdk21 AS build
LABEL authors="Nathan"
WORKDIR /app
COPY gradle gradle
COPY gradlew .
COPY build.gradle.kts .
RUN ./gradlew dependencies --no-daemon || true
COPY src src
RUN ./gradlew bootJar --no-daemon

# Runtime stage
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]