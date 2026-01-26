package com.skypredict.client;

import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class PythonMlClient {

    private final RestClient restClient;

    public PythonMlClient(RestClient.Builder builder,
                          @Value("${python.service.base-url}") String baseUrl) {
        this.restClient = builder.baseUrl(baseUrl).build();
    }

    public Map<String, Object> getPrevisao(double lat, double lon, String data) {
        return restClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/previsao")
                        .queryParam("lat", lat)
                        .queryParam("lon", lon)
                        .queryParam("data", data)
                        .build())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
    }

    public Map<String, Object> sugerirRota(String origemId, String destinoId, String data) {
        return restClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/sugerir_rota")
                        .queryParam("origem_id", origemId)
                        .queryParam("destino_id", destinoId)
                        .queryParam("data", data)
                        .build())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
    }
}
