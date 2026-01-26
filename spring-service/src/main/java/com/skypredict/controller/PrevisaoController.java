package com.skypredict.controller;

import java.util.Map;

import com.skypredict.client.PythonMlClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PrevisaoController {

    private final PythonMlClient pythonMlClient;

    public PrevisaoController(PythonMlClient pythonMlClient) {
        this.pythonMlClient = pythonMlClient;
    }

    @GetMapping("/previsao")
    public ResponseEntity<Map<String, Object>> getPrevisao(
            @RequestParam double lat,
            @RequestParam double lon,
            @RequestParam String data) {
        return ResponseEntity.ok(pythonMlClient.getPrevisao(lat, lon, data));
    }
}
