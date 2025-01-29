import os
import argparse
import random
import json

from typing import List, Dict

DEFAULT_RANDOM_SEED = 123
DEFAULT_NUMBER_OF_RESTAURANTS_TO_GENERATE = 1000
MINIMUM_PRICE = 3


DISTRICT_SETTINGS = {
    "North District": {
        "relative_number_of_restaurants": 1,
        "price_mu": 50,
        "price_sigma": 20,
        "minimum_price": 15,
        "relative_cuisine_weights": {
            "italian": 1,
            "greek": 0,
            "mexican": 0,
            "japanese": 1,
            "indian": 0,
        },
    },
    "East District": {
        "relative_number_of_restaurants": 2,
        "price_mu": 25,
        "price_sigma": 10,
        "minimum_price": 8,
        "relative_cuisine_weights": {
            "italian": 0,
            "greek": 0,
            "mexican": 1,
            "japanese": 2,
            "indian": 1,
        },
    },
    "South District": {
        "relative_number_of_restaurants": 2,
        "price_mu": 15,
        "price_sigma": 10,
        "minimum_price": 5,
        "relative_cuisine_weights": {
            "italian": 1,
            "greek": 3,
            "mexican": 2,
            "japanese": 0,
            "indian": 0,
        },
    },
    "West District": {
        "relative_number_of_restaurants": 1,
        "price_mu": 10,
        "price_sigma": 5,
        "minimum_price": 3,
        "relative_cuisine_weights": {
            "italian": 1,
            "greek": 1,
            "mexican": 0,
            "japanese": 0,
            "indian": 2,
        },
    },
}

WORDS_FOR_NAME_A = [
    "",
    "New",
    "Old",
    "Little",
    "Big",
    "Great",
    "Perfect",
    "Good",
]

WORDS_FOR_NAME_C = [
    "",
    "Garden",
    "Express",
    "House",
]

CUISINE_OPTIONS = {
    "italian": {
        "dishes": ["pasta", "pizza", "lasagna", "risotto", "pesto", "gelato"],
        "words_for_name_b": [
            "Italy",
            "Rome",
            "Florence",
            "Venice",
            "Milan",
            "Turin",
            "Naples",
            "Palermo",
            "Catania",
        ],
    },
    "greek": {
        "dishes": [
            "greek salad",
            "mousaka",
            "tzatziki",
            "pastitsio",
            "cheese pie",
            "spinach pie",
        ],
        "words_for_name_b": [
            "Greece",
            "Athens",
            "Thessaloniki",
            "Santorini",
            "Mykonos",
            "Paros",
            "Corfu",
            "Acropolis",
            "Parthenon",
        ],
    },
    "mexican": {
        "dishes": [
            "tacos",
            "burritos",
            "quesadillas",
            "churros",
            "guacamole",
            "carnitas",
        ],
        "words_for_name_b": [
            "Mexico",
            "Tijuana",
            "Guadalajara",
            "Monterrey",
            "Mexicali",
            "Toluca",
            "Oaxaca",
            "Xalapa",
            "Guadalupe",
        ],
    },
    "japanese": {
        "dishes": ["ramen", "sushi", "sashimi", "miso soup", "okonomiyaki", "tonkatsu"],
        "words_for_name_b": [
            "Japan",
            "Tokyo",
            "Kyoto",
            "Osaka",
            "Nagoya",
            "Kobe",
            "Sapporo",
            "Fukuoka",
            "Toyama",
        ],
    },
    "indian": {
        "dishes": [
            "samosa",
            "biryani",
            "naan",
            "butter chicken",
            "rogan josh",
            "tandoori chicken",
        ],
        "words_for_name_b": [
            "India",
            "Mumbai",
            "Bengaluru",
            "Kolkata",
            "Pune",
            "Jaipur",
            "Raipur",
            "Surat",
            "Kochi",
        ],
    },
}

ALL_DISTRICTS = list(DISTRICT_SETTINGS.keys())
RELATIVE_NUMBER_OF_RESTAURANTS_SUM = sum(
    [value["relative_number_of_restaurants"] for value in DISTRICT_SETTINGS.values()]
)
ALL_CUISINES = list(CUISINE_OPTIONS.keys())


def _get_args():
    parser = argparse.ArgumentParser(description="Generate restaurant descriptions")

    parser.add_argument(
        "--output-directory",
        help="Directory where output data will stored.",
        type=str,
        required=True,
    )

    parser.add_argument(
        "--random-seed",
        help=f"Seed for random number generator. Default value is {DEFAULT_RANDOM_SEED}.",
        type=int,
        default=DEFAULT_RANDOM_SEED,
    )

    parser.add_argument(
        "--number-of-restaurants",
        help=f"Number of restaurants to generate. Default value is {DEFAULT_NUMBER_OF_RESTAURANTS_TO_GENERATE}.",
        type=int,
        default=DEFAULT_NUMBER_OF_RESTAURANTS_TO_GENERATE,
    )

    return parser.parse_args()


def _add_commas_plus_and(words: List[str]) -> str:
    if len(words) == 1:
        return words[0]
    else:
        return f"""{", ".join(words[:-1])} and {words[-1]}"""


def _get_restaurant_description(metadata) -> str:
    return f"""
{metadata["restaurant_name"]} is a restaurant with {metadata["restaurant_cuisine"]} cuisine
in {metadata["district_name"]} serving {_add_commas_plus_and(metadata["dishes"])}.
Their signature dish is {metadata["signature_dish"]}. 
The average price per person is ${metadata["average_price_per_person"]}. 
Customers have rated its food with {metadata["rating_food_stars"]} stars on average. 
The service has average rating of {metadata["rating_service_stars"]} stars.
    """


def _get_random_cuisine(district: str) -> str:
    weights = DISTRICT_SETTINGS[district]["relative_cuisine_weights"]
    options = [cuisine for cuisine, w in weights.items() for _ in range(w)]
    return random.choice(options)


def _get_random_dishes(cuisine: str) -> List[str]:
    dishes_count = random.randint(2, 4)
    options = CUISINE_OPTIONS[cuisine]["dishes"]
    return random.sample(options, k=dishes_count)


def _get_random_price(district: str) -> str:
    options = DISTRICT_SETTINGS[district]

    price = -1
    while price < options["minimum_price"]:
        price = random.gauss(mu=options["price_mu"], sigma=options["price_sigma"])
    return price


def _get_random_restaurant_metadata(
    district: str, remaining_restaurant_names: Dict[str, List[str]]
) -> Dict:
    cuisine = _get_random_cuisine(district=district)

    restaurant_name = remaining_restaurant_names[cuisine].pop()

    dishes = _get_random_dishes(cuisine=cuisine)
    price = int(_get_random_price(district=district))

    return {
        "district_name": district,
        "restaurant_name": restaurant_name,
        "restaurant_cuisine": cuisine,
        "signature_dish": dishes[0],
        "dishes": dishes[1:],
        "average_price_per_person": price,
        "rating_food_stars": random.randint(1, 5),
        "rating_service_stars": random.randint(1, 5),
    }


def _combine_words_into_name(words: List[str]):
    # I combine them into a single word without spaces
    # to make it look more like unique names.
    return "".join([w for w in words if w != ""])


def _build_names_for_cuisine(cuisine: str):
    all_names = [
        _combine_words_into_name([w1, w2, w3])
        for w1 in WORDS_FOR_NAME_A
        for w2 in CUISINE_OPTIONS[cuisine]["words_for_name_b"]
        for w3 in WORDS_FOR_NAME_C
    ]
    random.shuffle(all_names)
    return all_names


def main():
    args = _get_args()
    random.seed(args.random_seed)

    current_restaurant = 1
    all_metadata = []

    remaining_restaurant_names = {
        cuisine: _build_names_for_cuisine(cuisine=cuisine) for cuisine in ALL_CUISINES
    }

    descriptions_dir = os.path.join(args.output_directory, "descriptions")
    if not os.path.exists(descriptions_dir):
        os.makedirs(descriptions_dir)

    while current_restaurant <= args.number_of_restaurants:
        district = random.choice(ALL_DISTRICTS)
        if (
            random.randint(0, RELATIVE_NUMBER_OF_RESTAURANTS_SUM)
            < DISTRICT_SETTINGS[district]["relative_number_of_restaurants"]
        ):
            metadata = _get_random_restaurant_metadata(
                district, remaining_restaurant_names=remaining_restaurant_names
            )
            description = _get_restaurant_description(metadata)

            with open(
                os.path.join(
                    descriptions_dir, f"restaurant-{current_restaurant:04}.txt"
                ),
                "w",
                encoding="UTF-8",
            ) as f:
                f.write(description)

            all_metadata.append(metadata)
            current_restaurant += 1

    with open(
        os.path.join(args.output_directory, "restaurant-metadata.json"), "w"
    ) as f:
        json.dump(all_metadata, f, indent=4)


if __name__ == "__main__":
    main()
