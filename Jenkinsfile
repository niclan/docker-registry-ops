#!/usr/bin/env groovy

def team    = 'vg'
def project = 'ops'
def name    = 'docker-registry-monitor'
def email   = 'nicolai.langfeldt@schibsted.com'

def stagedRelease = createRelease(
  team: team,
  project: project,
  name: name,
  email: email,
  clusters: [ 'vg-k8s' ],
  logging: 'stdout',
  ports: [[
    name: 'http',
    port: 8000,
    protocol: 'tcp',
    healthcheck: [
      enabled: true,
      protocol: 'http',
      path: '/health'
    ],
    expose: [
      enabled: true,
      whitelist: [ '0.0.0.0/0'],
      forceTLS: true
    ]
  ]],
  slack: [
    enabled: false,
    channel: '#vg-ops-notify',
    environments: ['production'],
    tokenCredentialId: 'slack-jenkins-app'
  ],
  secrets: [
    enabled: true,
    source: 'vault',
    path: 'VG',
    keys: [ 'APIKEY' ]
  ]
)

buildRelease(
  release: stagedRelease
)

deployRelease(
  release: stagedRelease,
  environment: 'staging',
  manualJudgement: false,
  instances: 1,
  resources: [ cpus: 1, memory: 2048 ],
  k8s: [
    ingress: [
      annotations: [
        'nginx.ingress.kubernetes.io/proxy-body-size': '100m',
        'nginx.ingress.kubernetes.io/client-body-buffer-size': '100m'
      ]
    ]
  ]
)


if (env.BRANCH_NAME == 'master') {
   deployRelease(
     release: stagedRelease,
     environment: 'production',
     manualJudgement: true,
     instances: 1,
     resources: [ cpus: 1, memory: 2048 ],
     k8s: [
       ingress: [
         annotations: [
           'nginx.ingress.kubernetes.io/proxy-body-size': '100m',
           'nginx.ingress.kubernetes.io/client-body-buffer-size': '100m'
         ]
       ]
     ]
   )
}
