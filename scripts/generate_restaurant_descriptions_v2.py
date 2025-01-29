import os
import argparse
import random
import json
from string import ascii_lowercase

from typing import List, Dict

DEFAULT_RANDOM_SEED = 123
DEFAULT_NUMBER_OF_RESTAURANTS_TO_GENERATE = 1000
MINIMUM_PRICE = 3
NUMBER_OF_USERS = 200
MIN_REVIEWS_PER_RESTAURANT = 1
MAX_REVIEWS_PER_RESTAURANT = 20
MIN_RESTAURANT_CAPACITY = 0
MAX_RESTAURANT_CAPACITY = 10

POSITIVE_ADJECTIVES_FOR_DISHES = [
    "good",
    "great",
    "nice",
    "tasty",
    "delicious",
    "fresh",
    "excellent",
]

NEGATIVE_ADJECTIVES_FOR_DISHES = [
    "mediocre",
    "disgusting",
    "awful",
    "bad",
    "horrible",
]

DISTRICT_SETTINGS = {
    "North District": {
        "relative_number_of_restaurants": 1,
        "price_mu": 50,
        "price_sigma": 20,
        "minimum_price": 15,
        "relative_cuisine_weights": {
            "Italian": 1,
            "Greek": 0,
            "Mexican": 0,
            "Japanese": 1,
            "Indian": 0,
        },
    },
    "East District": {
        "relative_number_of_restaurants": 2,
        "price_mu": 25,
        "price_sigma": 10,
        "minimum_price": 8,
        "relative_cuisine_weights": {
            "Italian": 0,
            "Greek": 0,
            "Mexican": 1,
            "Japanese": 2,
            "Indian": 1,
        },
    },
    "South District": {
        "relative_number_of_restaurants": 2,
        "price_mu": 15,
        "price_sigma": 10,
        "minimum_price": 5,
        "relative_cuisine_weights": {
            "Italian": 1,
            "Greek": 3,
            "Mexican": 2,
            "Japanese": 0,
            "Indian": 0,
        },
    },
    "West District": {
        "relative_number_of_restaurants": 1,
        "price_mu": 10,
        "price_sigma": 5,
        "minimum_price": 3,
        "relative_cuisine_weights": {
            "Italian": 1,
            "Greek": 1,
            "Mexican": 0,
            "Japanese": 0,
            "Indian": 2,
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
    "Italian": {
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
    "Greek": {
        "dishes": [
            "Greek salad",
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
    "Mexican": {
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
    "Japanese": {
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
    "Indian": {
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
        "capacity_persons": random.randint(
            MIN_RESTAURANT_CAPACITY, MAX_RESTAURANT_CAPACITY
        ),
    }


def _get_random_ip_address() -> str:
    return ".".join(str(random.randint(0, 255)) for _ in range(4))


def _get_random_word(n_characters: int) -> str:
    return "".join(random.choice(ascii_lowercase) for i in range(n_characters))


def _get_random_email() -> str:
    first_name = _get_random_word(random.randint(2, 10))
    last_name = _get_random_word(random.randint(2, 10))
    domain = _get_random_word(random.randint(5, 10)) + ".com"
    return f"{first_name}.{last_name}@{domain}"


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


def _build_users_details():
    return [
        {"email": _get_random_email(), "ip_address": _get_random_ip_address()}
        for _ in range(NUMBER_OF_USERS)
    ]


def _get_food_adjective(rating_food_stars) -> str:
    positive_weight = (rating_food_stars - 1) / 4.0
    adjectives_pool = (
        POSITIVE_ADJECTIVES_FOR_DISHES
        if random.random() <= positive_weight
        else NEGATIVE_ADJECTIVES_FOR_DISHES
    )

    return random.choice(adjectives_pool)


def _build_single_review(user, dishes, rating_food_stars) -> str:
    dish = random.choice(dishes)
    adjective = _get_food_adjective(rating_food_stars)
    return f"""
{user["email"]} ({user["ip_address"]}): The {dish} is {adjective}
    """


def _build_random_reviews(all_users, restaurant_metadata) -> str:
    reviews = """
Reviews:
    """
    number_of_reviews = random.randint(
        MIN_REVIEWS_PER_RESTAURANT, MAX_REVIEWS_PER_RESTAURANT
    )
    users = random.sample(all_users, k=number_of_reviews)

    all_dishes = restaurant_metadata["dishes"]
    all_dishes.append(restaurant_metadata["signature_dish"])

    for i in range(number_of_reviews):
        user = users[i]
        reviews += _build_single_review(
            user, all_dishes, restaurant_metadata["rating_food_stars"]
        )

    return reviews


def main():
    args = _get_args()
    random.seed(args.random_seed)

    current_restaurant = 1
    all_metadata = []

    remaining_restaurant_names = {
        cuisine: _build_names_for_cuisine(cuisine=cuisine) for cuisine in ALL_CUISINES
    }

    all_users = _build_users_details()

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
            description += _build_random_reviews(all_users, metadata)

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
