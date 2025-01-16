
# Amazon Bedrock AI Agents with AWS CDK

For prerequisites and how to bootstrap your AWS environment see the official documentation
- [Getting started with the AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)
- [Bootstrap your environment for use with the AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping-env.html)

To deploy the solution

- `make generate-data` (not needed, data is stored in this repo)
- `make login-ecr
- `export CDK_DEFAULT_ACCOUNT=<AWS account number>`
- `cdk deploy` (or `cdk deploy --require-approval never`)

To destroy it

- Delete the cloudformation template in the Console
- or just run `cdk destroy` from the command line
