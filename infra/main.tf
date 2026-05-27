# Terraform skeleton for SurveySparrow AWS deployment.
# Region: ap-south-1 (Mumbai) — adjust to match SurveySparrow's existing footprint.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.40" }
  }
  backend "s3" {
    bucket = "ss-terraform-state"
    key    = "se-demo-assessment-agent/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" { default = "ap-south-1" }
variable "env"        { default = "prod" }

# ----------------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------------
resource "aws_s3_bucket" "reports" {
  bucket = "ss-se-reports-${var.env}"
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_dynamodb_table" "calls" {
  name         = "ss_se_calls_${var.env}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "call_id"
  attribute {
    name = "call_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "scores" {
  name         = "ss_se_scores_${var.env}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "se_name"
  range_key    = "month"
  attribute { name = "se_name"; type = "S" }
  attribute { name = "month";   type = "S" }
}

resource "aws_dynamodb_table" "benchmarks" {
  name         = "ss_se_industry_benchmarks_${var.env}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "criterion"
  attribute { name = "criterion"; type = "S" }
}

# ----------------------------------------------------------------------------
# Compute
# ----------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "ss-se-coach-${var.env}"
}

# Pulls image from SurveySparrow's internal ECR (built from Bitbucket main)
resource "aws_ecs_task_definition" "analyzer" {
  family                   = "ss-se-coach-analyzer-${var.env}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "analyzer"
    image = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/se-coach:latest"
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic.arn },
      { name = "HUBSPOT_TOKEN",     valueFrom = aws_secretsmanager_secret.hubspot.arn },
      { name = "RECALL_API_KEY",    valueFrom = aws_secretsmanager_secret.recall.arn },
      { name = "AVOMA_API_KEY",     valueFrom = aws_secretsmanager_secret.avoma.arn },
    ]
  }])
}

# ----------------------------------------------------------------------------
# Scheduled monthly run (1st of each month, 06:00 IST)
# ----------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "monthly" {
  name                = "ss-se-coach-monthly-${var.env}"
  schedule_expression = "cron(30 0 1 * ? *)" # 06:00 IST = 00:30 UTC
}

resource "aws_cloudwatch_event_target" "monthly_run" {
  rule      = aws_cloudwatch_event_rule.monthly.name
  target_id = "ecs"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.events.arn
  ecs_target {
    task_definition_arn = aws_ecs_task_definition.analyzer.arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = data.aws_subnets.private.ids
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }
}

# ----------------------------------------------------------------------------
# Recall.ai webhook → Lambda → SQS → ECS (real-time call analysis after each call)
# ----------------------------------------------------------------------------
resource "aws_sqs_queue" "ingest" {
  name                       = "ss-se-coach-ingest-${var.env}"
  visibility_timeout_seconds = 900
}

resource "aws_lambda_function" "webhook" {
  function_name = "ss-se-coach-webhook-${var.env}"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/se-coach-webhook:latest"
  timeout       = 30
  environment {
    variables = { SQS_URL = aws_sqs_queue.ingest.url }
  }
}

resource "aws_apigatewayv2_api" "webhook" {
  name          = "ss-se-coach-webhook-${var.env}"
  protocol_type = "HTTP"
}

# ----------------------------------------------------------------------------
# Secrets & IAM (stubs — fill in with SurveySparrow's policy library)
# ----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "anthropic" { name = "ss/se-coach/anthropic/${var.env}" }
resource "aws_secretsmanager_secret" "hubspot"   { name = "ss/se-coach/hubspot/${var.env}" }
resource "aws_secretsmanager_secret" "recall"    { name = "ss/se-coach/recall/${var.env}" }
resource "aws_secretsmanager_secret" "avoma"     { name = "ss/se-coach/avoma/${var.env}" }

resource "aws_iam_role" "ecs_task"   { name = "ss-se-coach-ecs-${var.env}";   assume_role_policy = "{}" }
resource "aws_iam_role" "lambda"     { name = "ss-se-coach-lambda-${var.env}"; assume_role_policy = "{}" }
resource "aws_iam_role" "events"     { name = "ss-se-coach-events-${var.env}"; assume_role_policy = "{}" }

resource "aws_security_group" "ecs" { name = "ss-se-coach-ecs-${var.env}" }

# ----------------------------------------------------------------------------
# Data lookups
# ----------------------------------------------------------------------------
data "aws_caller_identity" "current" {}
data "aws_subnets" "private" {
  filter { name = "tag:Tier"; values = ["private"] }
}
