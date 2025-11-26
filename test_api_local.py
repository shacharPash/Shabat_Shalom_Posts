from api.poster import build_poster_from_payload


def main():
    payload = {
        "message": "שבת שלום מה-API הלוגי!",
        "leiluyNeshama": "אורי בורנשטיין הי\"ד"
    }

    poster_bytes = build_poster_from_payload(payload)

    output_path = "test_api_poster.png"
    with open(output_path, "wb") as f:
        f.write(poster_bytes)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

