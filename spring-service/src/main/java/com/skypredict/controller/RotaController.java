package com.skypredict.controller;

import java.util.Map;

import com.skypredict.client.PythonMlClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RotaController {

    private final PythonMlClient pythonMlClient;

    public RotaController(PythonMlClient pythonMlClient) {
        this.pythonMlClient = pythonMlClient;
    }

    @GetMapping("/sugerir_rota")
    public ResponseEntity<Map<String, Object>> sugerirRota(
            @RequestParam("origem_id") String origemId,
            @RequestParam("destino_id") String destinoId,
            @RequestParam String data) {
        return ResponseEntity.ok(pythonMlClient.sugerirRota(origemId, destinoId, data));
    }
}
