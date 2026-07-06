from pipelines.run_medallion import main, run_player_recent_form_pipeline


def build_recent_form(write_csv=True):
    result = run_player_recent_form_pipeline(write_csv=write_csv)
    gold = result["gold"]
    return gold["rows"], gold["path"]


if __name__ == "__main__":
    main()
