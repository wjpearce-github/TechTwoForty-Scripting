import argparse
import boto3


def parse_args():
    p = argparse.ArgumentParser(description="Audit an AWS account for common risks.")
    p.add_argument("--checks", nargs="+", default=["s3", "iam"],
                   help="Which checks to run (s3, iam).")
    p.add_argument("--key-age-days", type=int, default=90,
                   help="Flag IAM keys unused beyond this many days.")
    return p.parse_args()


def check_public_buckets(s3):
    findings = []
    for bucket in s3.list_buckets()["Buckets"]:
        name = bucket["Name"]
        try:
            cfg = s3.get_public_access_block(Bucket=name)
            block = cfg["PublicAccessBlockConfiguration"]
            if not all(block.values()):
                findings.append(f"S3 bucket '{name}' is not fully blocking public access")
        except s3.exceptions.ClientError:
            findings.append(f"S3 bucket '{name}' has NO public access block configured")
    return findings


from datetime import datetime, timezone, timedelta


def check_stale_keys(iam, max_age_days):
    findings = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    for user in iam.list_users()["Users"]:
        uname = user["UserName"]
        for key in iam.list_access_keys(UserName=uname)["AccessKeyMetadata"]:
            kid = key["AccessKeyId"]
            last = iam.get_access_key_last_used(AccessKeyId=kid)
            used = last["AccessKeyLastUsed"].get("LastUsedDate")
            if used is None or used < cutoff:
                findings.append(f"IAM key {kid} for '{uname}' is unused/stale")
    return findings


def main():
    args = parse_args()
    all_findings = []
    if "s3" in args.checks:
        print("Checking S3 buckets...")
        all_findings += check_public_buckets(boto3.client("s3"))
    if "iam" in args.checks:
        print("Checking IAM access keys...")
        all_findings += check_stale_keys(boto3.client("iam"), args.key_age_days)
    if all_findings:
        print(f"{len(all_findings)} issue(s) found:")
        for f in all_findings:
            print(f"  - {f}")
    else:
        print("No issues found.")


if __name__ == "__main__":
    main()
