---
name: add-sonarqube
description: Add SonarQube static analysis as a reusable step template in this pipeline template repository.
---

Add SonarQube code quality scanning to the pipeline template library.

## Steps

1. Read the existing step templates in `steps/` to understand naming and parameter conventions
2. Create `steps/sonarqube-scan.yml`:

```yaml
parameters:
  - name: projectKey
    type: string
  - name: projectName
    type: string
  - name: sonarEndpoint
    type: string
    default: SonarQube
  - name: extraProperties
    type: string
    default: ''

steps:
  - task: SonarQubePrepare@6
    displayName: SonarQube — prepare analysis
    inputs:
      SonarQube: ${{ parameters.sonarEndpoint }}
      scannerMode: CLI
      configMode: manual
      cliProjectKey: ${{ parameters.projectKey }}
      cliProjectName: ${{ parameters.projectName }}
      extraProperties: |
        sonar.sources=.
        ${{ parameters.extraProperties }}

  - task: SonarQubeAnalyze@6
    displayName: SonarQube — run analysis

  - task: SonarQubePublish@6
    displayName: SonarQube — publish results
    inputs:
      pollingTimeoutSec: 300
```

3. Identify where in `stages/build.yml` the scan should be inserted:
   - After checkout/restore but before compilation (so analysis covers uncompiled source)
   - Alternatively, after test execution if test coverage is to be included
4. Add an optional `runSonarQube: boolean` parameter to `stages/build.yml` with `${{ if parameters.runSonarQube }}` guard
5. Document the required ADO service connection name convention (`SonarQube` by default)

## Output

Show the new `steps/sonarqube-scan.yml` and the diff to `stages/build.yml`. Note which SonarQube task extension version is required and any language-specific `extraProperties` examples.
