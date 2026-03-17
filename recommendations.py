RECOMMENDATIONS = {
    "Historic": [
        {
            "name": "Hampi",
            "desc": "Ancient city of the Vijayanagara Empire.Filled with temple ruins, stone chariots, and massive monuments.",
            "image": "static/hampi.png"
        },
        {
            "name": "Great Wall of China",
            "desc":"Historic Wall Built to Protect Empires.",
            "image": "static/great-wall-of-china.png"
        }
    ],

    "Adventure": [
        {
            "name": "Manali",
            "desc": "Snow mountains and adventure sports.",
            "image": "static/manali.png"
        },
        {
            "name": "Mount Everest",
            "desc": "Ultimate Challenge for Mountain Climbers",
            "image": "static/mount-everest.png"
        }
    ],

    "Chilling": [
        {
            "name": "Varkala",
            "desc": "Scenic Cliffs Overlooking the Arabian Sea.”",
            "image": "static/varkala.png"
        },
        {
            "name": "Bali",
            "desc": "Beautiful Beaches and Serene Temples.",
            "image": "static/bali.png"
        }
    ],

    "Pilgrimage": [
        {
            "name": "Tirupati",
            "desc": "One of the most sacred temples in India.",
            "image": "static/tirupati.png"
        },
        {
            "name": "Varanasi",
            "desc": "Spiritual city on the banks of the Ganges.",
            "image": "static/varanasi.png"
        }
    ],

    "Nature": [
        {
            "name": "Kerala",
            "desc": "Backwaters, greenery and houseboats.",
            "image": "static/kerala.png"
        },
        {
            "name": "Ladakh",
            "desc": "Known for snow-covered mountains, lakes, and stunning landscapes.",
            "image": "static/ladakh.png"
        }
    ]
}


def get_recommendations(preferences):
    results = []

    for pref in preferences:
        if pref in RECOMMENDATIONS:
            results.extend(RECOMMENDATIONS[pref])

    return results